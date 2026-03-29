from __future__ import annotations

import argparse
import json
import os
import re
import zipfile
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

import psycopg
import requests
from dotenv import load_dotenv
from psycopg.rows import dict_row


# =========================================================
# env
# =========================================================

load_dotenv()
load_dotenv(".env.local", override=False)

DATABASE_URL = os.getenv("DATABASE_URL")
KRX_AUTH_KEY = os.getenv("KRX_AUTH_KEY")
DART_API_KEY = os.getenv("DART_API_KEY")

# KRX 문서 샘플 요청 경로는 /svc/sample/apis/sto/... 형태로 보임.
# 승인 후 문서에 실제 운영 base path가 다르면 .env.local 에서 바꿔주세요.
KRX_API_BASE = os.getenv("KRX_API_BASE", "https://openapi.krx.co.kr/svc/sample/apis/sto")
DART_API_BASE = "https://opendart.fss.or.kr/api"

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL 환경변수가 필요합니다.")
if not KRX_AUTH_KEY:
    raise RuntimeError("KRX_AUTH_KEY 환경변수가 필요합니다.")
if not DART_API_KEY:
    raise RuntimeError("DART_API_KEY 환경변수가 필요합니다.")


# =========================================================
# util
# =========================================================

def yyyymmdd(d: date) -> str:
    return d.strftime("%Y%m%d")


def parse_yyyymmdd(v: Any) -> Optional[date]:
    if v is None:
        return None
    s = re.sub(r"[^0-9]", "", str(v).strip())
    if len(s) != 8:
        return None
    try:
        return datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        return None


def normalize_text(v: Any) -> str:
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def normalize_stock_code(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = re.sub(r"\D", "", str(v))
    if not s:
        return None
    return s.zfill(6)


def normalize_holder_key(v: Any) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", normalize_text(v).lower())


def to_decimal(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    s = str(v).strip()
    if not s or s == "-":
        return None
    s = s.replace(",", "")
    try:
        return Decimal(s)
    except Exception:
        return None


def to_int(v: Any) -> Optional[int]:
    d = to_decimal(v)
    return int(d) if d is not None else None


def pick(row: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, "", "-"):
            return row[key]
    return None


def previous_business_day(ref: Optional[date] = None) -> date:
    d = ref or date.today()
    if d.weekday() == 0:
        return d - timedelta(days=3)
    if d.weekday() == 6:
        return d - timedelta(days=2)
    if d.weekday() == 5:
        return d - timedelta(days=1)
    return d - timedelta(days=1)


# =========================================================
# db
# =========================================================

def get_conn(autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=autocommit)


def start_sync_run(job_name: str, run_date: date) -> int:
    with get_conn(autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            """
            insert into public.sync_runs (job_name, run_date, status)
            values (%s, %s, 'RUNNING')
            returning id
            """,
            (job_name, run_date),
        )
        return cur.fetchone()["id"]


def finish_sync_run(sync_run_id: int, status: str, stats: Dict[str, Any], error_message: Optional[str] = None) -> None:
    with get_conn(autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            """
            update public.sync_runs
            set status = %s,
                finished_at = now(),
                stats = %s,
                error_message = %s
            where id = %s
            """,
            (status, json.dumps(stats, ensure_ascii=False), error_message, sync_run_id),
        )


def fetch_active_companies(conn: psycopg.Connection, as_of: date) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select *
            from public.companies
            where is_active = true
              and tracking_expires_at >= %s
            order by listing_date desc
            """,
            (as_of,),
        )
        return list(cur.fetchall())


def upsert_company(conn: psycopg.Connection, row: Dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into public.companies (
                stock_code,
                dart_corp_code,
                company_name,
                company_name_eng,
                market_type,
                security_group,
                sector_name,
                industry,
                listing_date,
                tracking_started_at,
                tracking_expires_at,
                offering_price,
                offering_amount,
                offering_price_source,
                offering_price_source_rcept_no,
                par_value,
                listed_shares,
                homepage_url,
                ir_url,
                current_price,
                current_price_date,
                return_since_ipo,
                is_active
            )
            values (
                %(stock_code)s,
                %(dart_corp_code)s,
                %(company_name)s,
                %(company_name_eng)s,
                %(market_type)s,
                %(security_group)s,
                %(sector_name)s,
                %(industry)s,
                %(listing_date)s,
                %(tracking_started_at)s,
                %(tracking_expires_at)s,
                %(offering_price)s,
                %(offering_amount)s,
                %(offering_price_source)s,
                %(offering_price_source_rcept_no)s,
                %(par_value)s,
                %(listed_shares)s,
                %(homepage_url)s,
                %(ir_url)s,
                %(current_price)s,
                %(current_price_date)s,
                %(return_since_ipo)s,
                true
            )
            on conflict (stock_code) do update
            set
                dart_corp_code = excluded.dart_corp_code,
                company_name = excluded.company_name,
                company_name_eng = excluded.company_name_eng,
                market_type = excluded.market_type,
                security_group = excluded.security_group,
                sector_name = excluded.sector_name,
                industry = coalesce(excluded.industry, public.companies.industry),
                listing_date = excluded.listing_date,
                tracking_expires_at = excluded.tracking_expires_at,
                offering_price = coalesce(excluded.offering_price, public.companies.offering_price),
                offering_amount = coalesce(excluded.offering_amount, public.companies.offering_amount),
                offering_price_source = coalesce(excluded.offering_price_source, public.companies.offering_price_source),
                offering_price_source_rcept_no = coalesce(excluded.offering_price_source_rcept_no, public.companies.offering_price_source_rcept_no),
                par_value = coalesce(excluded.par_value, public.companies.par_value),
                listed_shares = coalesce(excluded.listed_shares, public.companies.listed_shares),
                homepage_url = coalesce(excluded.homepage_url, public.companies.homepage_url),
                ir_url = coalesce(excluded.ir_url, public.companies.ir_url),
                current_price = coalesce(excluded.current_price, public.companies.current_price),
                current_price_date = coalesce(excluded.current_price_date, public.companies.current_price_date),
                return_since_ipo = coalesce(excluded.return_since_ipo, public.companies.return_since_ipo),
                is_active = true
            """,
            row,
        )


def upsert_price_daily(conn: psycopg.Connection, company_id: str, row: Dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into public.price_daily (
                company_id,
                trade_date,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
                trade_value,
                market_cap,
                shares_outstanding,
                source,
                raw_payload
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'KRX_OPEN_API', %s)
            on conflict (company_id, trade_date) do update
            set
                open_price = excluded.open_price,
                high_price = excluded.high_price,
                low_price = excluded.low_price,
                close_price = excluded.close_price,
                volume = excluded.volume,
                trade_value = excluded.trade_value,
                market_cap = excluded.market_cap,
                shares_outstanding = excluded.shares_outstanding,
                raw_payload = excluded.raw_payload
            """,
            (
                company_id,
                row["trade_date"],
                row["open_price"],
                row["high_price"],
                row["low_price"],
                row["close_price"],
                row["volume"],
                row["trade_value"],
                row["market_cap"],
                row["shares_outstanding"],
                json.dumps(row["raw_payload"], ensure_ascii=False),
            ),
        )


def update_company_market_snapshot(
    conn: psycopg.Connection,
    company_id: str,
    trade_date: date,
    close_price: Optional[Decimal],
    return_since_ipo: Optional[Decimal],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            update public.companies
            set current_price = %s,
                current_price_date = %s,
                return_since_ipo = %s
            where id = %s
            """,
            (close_price, trade_date, return_since_ipo, company_id),
        )


def upsert_disclosure(
    conn: psycopg.Connection,
    company_id: str,
    stock_code: str,
    dart_corp_code: str,
    row: Dict[str, Any],
) -> None:
    rcept_no = normalize_text(row.get("rcept_no"))
    rcept_dt = parse_yyyymmdd(row.get("rcept_dt"))
    pblntf_ty = normalize_text(row.get("pblntf_ty"))
    pblntf_detail_ty = normalize_text(row.get("pblntf_detail_ty"))

    is_shareholder_related = (
        pblntf_ty == "D"
        or pblntf_detail_ty in {"D001", "D002", "D003", "D004", "D005"}
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            insert into public.disclosures (
                rcept_no,
                company_id,
                dart_corp_code,
                stock_code,
                rcept_dt,
                report_nm,
                pblntf_ty,
                pblntf_detail_ty,
                corp_cls,
                flr_nm,
                rm,
                disclosure_url,
                is_shareholder_related,
                raw_payload
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (rcept_no) do update
            set
                company_id = excluded.company_id,
                dart_corp_code = excluded.dart_corp_code,
                stock_code = excluded.stock_code,
                rcept_dt = excluded.rcept_dt,
                report_nm = excluded.report_nm,
                pblntf_ty = excluded.pblntf_ty,
                pblntf_detail_ty = excluded.pblntf_detail_ty,
                corp_cls = excluded.corp_cls,
                flr_nm = excluded.flr_nm,
                rm = excluded.rm,
                disclosure_url = excluded.disclosure_url,
                is_shareholder_related = excluded.is_shareholder_related,
                raw_payload = excluded.raw_payload
            """,
            (
                rcept_no,
                company_id,
                dart_corp_code,
                stock_code,
                rcept_dt,
                normalize_text(row.get("report_nm")),
                pblntf_ty,
                pblntf_detail_ty,
                normalize_text(row.get("corp_cls")),
                normalize_text(row.get("flr_nm")),
                normalize_text(row.get("rm")),
                f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}",
                is_shareholder_related,
                json.dumps(row, ensure_ascii=False),
            ),
        )

        if rcept_dt:
            cur.execute(
                """
                update public.companies
                set latest_disclosure_date = greatest(coalesce(latest_disclosure_date, %s), %s)
                where id = %s
                """,
                (rcept_dt, rcept_dt, company_id),
            )


def upsert_shareholder_filing_raw(conn: psycopg.Connection, company_id: str, row: Dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into public.shareholder_filings_raw (
                company_id,
                rcept_no,
                dart_corp_code,
                corp_name,
                rcept_dt,
                report_tp,
                repror,
                stkqy,
                stkqy_irds,
                stkrt,
                stkrt_irds,
                ctr_stkqy,
                ctr_stkrt,
                report_resn,
                raw_payload
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (company_id, rcept_no, repror) do update
            set
                report_tp = excluded.report_tp,
                stkqy = excluded.stkqy,
                stkqy_irds = excluded.stkqy_irds,
                stkrt = excluded.stkrt,
                stkrt_irds = excluded.stkrt_irds,
                ctr_stkqy = excluded.ctr_stkqy,
                ctr_stkrt = excluded.ctr_stkrt,
                report_resn = excluded.report_resn,
                raw_payload = excluded.raw_payload
            """,
            (
                company_id,
                normalize_text(row.get("rcept_no")),
                normalize_text(row.get("corp_code")),
                normalize_text(row.get("corp_name")),
                parse_yyyymmdd(row.get("rcept_dt")),
                normalize_text(row.get("report_tp")),
                normalize_text(row.get("repror")),
                to_decimal(row.get("stkqy")),
                to_decimal(row.get("stkqy_irds")),
                to_decimal(row.get("stkrt")),
                to_decimal(row.get("stkrt_irds")),
                to_decimal(row.get("ctr_stkqy")),
                to_decimal(row.get("ctr_stkrt")),
                normalize_text(row.get("report_resn")),
                json.dumps(row, ensure_ascii=False),
            ),
        )


def rebuild_provisional_key_shareholder_latest(conn: psycopg.Connection, company: Dict[str, Any]) -> None:
    company_id = str(company["id"])
    listing_date: date = company["listing_date"]
    ipo_cutoff = listing_date + timedelta(days=120)

    with conn.cursor() as cur:
        cur.execute(
            """
            select *
            from public.shareholder_filings_raw
            where company_id = %s
            order by rcept_dt asc, id asc
            """,
            (company_id,),
        )
        raw_rows = list(cur.fetchall())

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in raw_rows:
        holder_name = normalize_text(row["repror"])
        if not holder_name:
            continue
        holder_key = normalize_holder_key(holder_name)
        grouped.setdefault(holder_key, []).append(row)

    with conn.cursor() as cur:
        cur.execute("delete from public.key_shareholder_latest where company_id = %s", (company_id,))

        total_change = Decimal("0")
        for holder_key, rows in grouped.items():
            rows.sort(key=lambda x: (x["rcept_dt"] or date(1900, 1, 1), x["id"]))
            ipo_candidates = [r for r in rows if r["rcept_dt"] and r["rcept_dt"] <= ipo_cutoff]
            ipo_row = ipo_candidates[0] if ipo_candidates else rows[0]
            latest_row = rows[-1]

            ipo_pct = ipo_row["stkrt"] or Decimal("0")
            latest_pct = latest_row["stkrt"] or Decimal("0")
            change_pct = latest_pct - ipo_pct
            total_change += change_pct

            cur.execute(
                """
                insert into public.key_shareholder_latest (
                    company_id,
                    holder_key,
                    holder_name,
                    holder_role,
                    ipo_base_pct,
                    latest_pct,
                    change_pct,
                    ipo_snapshot_date,
                    latest_snapshot_date,
                    latest_rcept_no,
                    is_new_holder,
                    is_exited_holder,
                    source,
                    raw_payload
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PROVISIONAL_DART_MAJORSTOCK', %s)
                """,
                (
                    company_id,
                    holder_key,
                    normalize_text(latest_row["repror"]) or normalize_text(ipo_row["repror"]),
                    normalize_text(latest_row["report_tp"]),
                    ipo_pct,
                    latest_pct,
                    change_pct,
                    ipo_row["rcept_dt"],
                    latest_row["rcept_dt"],
                    latest_row["rcept_no"],
                    ipo_pct == 0 and latest_pct > 0,
                    ipo_pct > 0 and latest_pct == 0,
                    json.dumps(
                        {
                            "ipo_row_id": ipo_row["id"],
                            "latest_row_id": latest_row["id"],
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

        cur.execute(
            """
            update public.companies
            set key_shareholders_change_pct = %s
            where id = %s
            """,
            (total_change, company_id),
        )


# =========================================================
# KRX
# =========================================================

class KRXClient:
    def __init__(self, auth_key: str, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"AUTH_KEY": auth_key})

    def _extract_rows(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        if isinstance(payload.get("OutBlock_1"), list):
            return payload["OutBlock_1"]
        if isinstance(payload.get("output"), list):
            return payload["output"]
        if isinstance(payload.get("result"), list):
            return payload["result"]
        return []

    def _get(self, endpoint: str, bas_dd: str) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/{endpoint}"
        resp = self.session.get(url, params={"basDd": bas_dd}, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        return self._extract_rows(payload)

    def fetch_base_info(self, market: str, bas_dd: str) -> List[Dict[str, Any]]:
        endpoint = "stk_isu_base_info" if market == "KOSPI" else "ksq_isu_base_info"
        rows = self._get(endpoint, bas_dd)

        out: List[Dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "stock_code": normalize_stock_code(
                        pick(row, "ISU_SRT_CD", "isuSrtCd", "SHORT_ISU_CD")
                    ),
                    "company_name": normalize_text(
                        pick(row, "ISU_ABBRV", "ISU_NM", "isuAbbrv", "isuNm")
                    ),
                    "company_name_eng": normalize_text(
                        pick(row, "ISU_ENG_NM", "isuEngNm")
                    ),
                    "listing_date": parse_yyyymmdd(
                        pick(row, "LIST_DD", "LIST_DT", "listDd")
                    ),
                    "market_type": market,
                    "security_group": normalize_text(
                        pick(row, "SECUGRP_NM", "secugrpNm")
                    ),
                    "sector_name": normalize_text(
                        pick(row, "SECT_TP_NM", "IND_TP_NM", "sectTpNm")
                    ),
                    "par_value": to_decimal(
                        pick(row, "PARVAL", "parval")
                    ),
                    "listed_shares": to_int(
                        pick(row, "LIST_SHRS", "listShrs")
                    ),
                    "raw_payload": row,
                }
            )

        return [r for r in out if r["stock_code"] and r["listing_date"]]

    def fetch_daily_trade(self, market: str, bas_dd: str) -> List[Dict[str, Any]]:
        endpoint = "stk_bydd_trd" if market == "KOSPI" else "ksq_bydd_trd"
        rows = self._get(endpoint, bas_dd)

        out: List[Dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "stock_code": normalize_stock_code(
                        pick(row, "ISU_SRT_CD", "isuSrtCd", "SHORT_ISU_CD")
                    ),
                    "trade_date": parse_yyyymmdd(
                        pick(row, "BAS_DD", "basDd")
                    ) or parse_yyyymmdd(bas_dd),
                    "open_price": to_decimal(
                        pick(row, "TDD_OPNPRC", "OPNPRC", "OPEN_PRC")
                    ),
                    "high_price": to_decimal(
                        pick(row, "TDD_HGPRC", "HGPRC", "HIGH_PRC")
                    ),
                    "low_price": to_decimal(
                        pick(row, "TDD_LWPRC", "LWPRC", "LOW_PRC")
                    ),
                    "close_price": to_decimal(
                        pick(row, "TDD_CLSPRC", "CLSPRC", "CLOSE_PRC")
                    ),
                    "volume": to_int(
                        pick(row, "ACC_TRDVOL", "ACC_TRD_VOL", "VOLUME")
                    ),
                    "trade_value": to_decimal(
                        pick(row, "ACC_TRDVAL", "ACC_TRD_VAL", "TRADE_VAL")
                    ),
                    "market_cap": to_decimal(
                        pick(row, "MKTCAP", "MKT_CAP")
                    ),
                    "shares_outstanding": to_int(
                        pick(row, "LIST_SHRS", "listShrs")
                    ),
                    "raw_payload": row,
                }
            )

        return [r for r in out if r["stock_code"] and r["trade_date"]]


# =========================================================
# OpenDART
# =========================================================

class DARTClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.session = requests.Session()

    def _get_json(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{DART_API_BASE}/{endpoint}"
        resp = self.session.get(url, params={"crtfc_key": self.api_key, **params}, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        status = payload.get("status")
        if status not in (None, "000", "013"):
            raise RuntimeError(f"DART error {status}: {payload.get('message')}")
        return payload

    def fetch_corp_code_map(self) -> Dict[str, str]:
        url = f"{DART_API_BASE}/corpCode.xml"
        resp = self.session.get(url, params={"crtfc_key": self.api_key}, timeout=60)
        resp.raise_for_status()

        zf = zipfile.ZipFile(BytesIO(resp.content))
        xml_name = zf.namelist()[0]
        xml_bytes = zf.read(xml_name)
        root = ET.fromstring(xml_bytes)

        mapping: Dict[str, str] = {}
        for item in root.findall(".//list"):
            corp_code = normalize_text(item.findtext("corp_code"))
            stock_code = normalize_stock_code(item.findtext("stock_code"))
            if corp_code and stock_code:
                mapping[stock_code] = corp_code
        return mapping

    def fetch_company_info(self, corp_code: str) -> Dict[str, Any]:
        payload = self._get_json("company.json", {"corp_code": corp_code})
        return payload

    def fetch_disclosures(self, corp_code: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        page_no = 1
        out: List[Dict[str, Any]] = []

        while True:
            payload = self._get_json(
                "list.json",
                {
                    "corp_code": corp_code,
                    "bgn_de": yyyymmdd(start_date),
                    "end_de": yyyymmdd(end_date),
                    "last_reprt_at": "Y",
                    "sort": "date",
                    "sort_mth": "desc",
                    "page_no": str(page_no),
                    "page_count": "100",
                },
            )

            rows = payload.get("list", [])
            out.extend(rows)

            total_page = int(payload.get("total_page", 1) or 1)
            if page_no >= total_page:
                break
            page_no += 1

        return out

    def fetch_majorstock(self, corp_code: str) -> List[Dict[str, Any]]:
        payload = self._get_json("majorstock.json", {"corp_code": corp_code})
        return payload.get("list", [])

    def fetch_equity_offering_terms(self, corp_code: str, listing_date: date) -> Dict[str, Any]:
        payload = self._get_json(
            "estkRs.json",
            {
                "corp_code": corp_code,
                "bgn_de": yyyymmdd(listing_date - timedelta(days=365)),
                "end_de": yyyymmdd(listing_date + timedelta(days=30)),
            },
        )

        candidates: List[Dict[str, Any]] = []
        for group in payload.get("group", []):
            title = normalize_text(group.get("title"))
            if title != "증권의종류":
                continue

            for row in group.get("list", []):
                row_copy = dict(row)
                row_copy["_group_title"] = title
                candidates.append(row_copy)

        if not candidates:
            return {}

        common_stock = [
            r for r in candidates
            if "보통주" in normalize_text(r.get("stksen"))
            or normalize_text(r.get("stksen")) == ""
        ]
        target_rows = common_stock if common_stock else candidates
        target_rows.sort(key=lambda r: normalize_text(r.get("rcept_no")), reverse=True)
        row = target_rows[0]

        return {
            "offering_price": to_decimal(row.get("slprc")),
            "offering_amount": to_decimal(row.get("slta")),
            "par_value": to_decimal(row.get("fv")),
            "source_rcept_no": normalize_text(row.get("rcept_no")),
            "raw_payload": row,
        }


# =========================================================
# sync jobs
# =========================================================

def seed_recent_universe(conn: psycopg.Connection, bas_dd: date) -> Dict[str, Any]:
    krx = KRXClient(KRX_AUTH_KEY, KRX_API_BASE)
    dart = DARTClient(DART_API_KEY)

    corp_code_map = dart.fetch_corp_code_map()

    base_rows: List[Dict[str, Any]] = []
    trade_rows: List[Dict[str, Any]] = []

    for market in ("KOSPI", "KOSDAQ"):
        base_rows.extend(krx.fetch_base_info(market, yyyymmdd(bas_dd)))
        trade_rows.extend(krx.fetch_daily_trade(market, yyyymmdd(bas_dd)))

    trade_map = {row["stock_code"]: row for row in trade_rows}
    seed_cutoff = bas_dd - timedelta(days=365)

    seeded = 0
    for row in base_rows:
        if row["listing_date"] < seed_cutoff:
            continue

        stock_code = row["stock_code"]
        corp_code = corp_code_map.get(stock_code)
        trade = trade_map.get(stock_code)

        homepage_url = None
        ir_url = None
        company_name_eng = row["company_name_eng"]
        if corp_code:
            try:
                company_info = dart.fetch_company_info(corp_code)
                homepage_url = normalize_text(company_info.get("hm_url")) or None
                ir_url = normalize_text(company_info.get("ir_url")) or None
                company_name_eng = normalize_text(company_info.get("corp_name_eng")) or company_name_eng
            except Exception:
                pass

        offering = {}
        if corp_code:
            try:
                offering = dart.fetch_equity_offering_terms(corp_code, row["listing_date"])
            except Exception:
                offering = {}

        offering_price = offering.get("offering_price")
        current_price = trade.get("close_price") if trade else None
        return_since_ipo = None
        if offering_price and current_price and offering_price != 0:
            return_since_ipo = ((current_price - offering_price) / offering_price) * Decimal("100")

        upsert_company(
            conn,
            {
                "stock_code": stock_code,
                "dart_corp_code": corp_code,
                "company_name": row["company_name"],
                "company_name_eng": company_name_eng,
                "market_type": row["market_type"],
                "security_group": row["security_group"],
                "sector_name": row["sector_name"],
                "industry": row["sector_name"],
                "listing_date": row["listing_date"],
                "tracking_started_at": bas_dd,
                "tracking_expires_at": row["listing_date"] + timedelta(days=365 * 3),
                "offering_price": offering.get("offering_price"),
                "offering_amount": offering.get("offering_amount"),
                "offering_price_source": "DART_ESTKRS" if offering.get("offering_price") else None,
                "offering_price_source_rcept_no": offering.get("source_rcept_no"),
                "par_value": offering.get("par_value") or row["par_value"],
                "listed_shares": row["listed_shares"],
                "homepage_url": homepage_url,
                "ir_url": ir_url,
                "current_price": current_price,
                "current_price_date": trade["trade_date"] if trade else None,
                "return_since_ipo": return_since_ipo,
            },
        )
        seeded += 1

    return {
        "seed_cutoff": yyyymmdd(seed_cutoff),
        "seeded_or_updated_companies": seeded,
    }


def sync_daily_prices(conn: psycopg.Connection, bas_dd: date) -> Dict[str, Any]:
    krx = KRXClient(KRX_AUTH_KEY, KRX_API_BASE)
    companies = fetch_active_companies(conn, bas_dd)
    if not companies:
        return {"updated_price_rows": 0}

    company_map = {c["stock_code"]: c for c in companies}

    all_trade_rows: List[Dict[str, Any]] = []
    for market in ("KOSPI", "KOSDAQ"):
        all_trade_rows.extend(krx.fetch_daily_trade(market, yyyymmdd(bas_dd)))

    updated = 0
    for row in all_trade_rows:
        company = company_map.get(row["stock_code"])
        if not company:
            continue

        upsert_price_daily(conn, str(company["id"]), row)

        offering_price = company["offering_price"]
        return_since_ipo = None
        if offering_price and row["close_price"] and offering_price != 0:
            return_since_ipo = ((row["close_price"] - offering_price) / offering_price) * Decimal("100")

        update_company_market_snapshot(
            conn,
            str(company["id"]),
            row["trade_date"],
            row["close_price"],
            return_since_ipo,
        )
        updated += 1

    return {
        "bas_dd": yyyymmdd(bas_dd),
        "updated_price_rows": updated,
    }


def sync_recent_disclosures(conn: psycopg.Connection, bas_dd: date, lookback_days: int = 7) -> Dict[str, Any]:
    dart = DARTClient(DART_API_KEY)
    companies = fetch_active_companies(conn, bas_dd)

    start_date = bas_dd - timedelta(days=lookback_days)
    count = 0

    for company in companies:
        corp_code = company["dart_corp_code"]
        if not corp_code:
            continue

        try:
            rows = dart.fetch_disclosures(corp_code, start_date, bas_dd)
        except Exception:
            continue

        for row in rows:
            upsert_disclosure(
                conn,
                str(company["id"]),
                company["stock_code"],
                corp_code,
                row,
            )
            count += 1

    return {
        "start_date": yyyymmdd(start_date),
        "end_date": yyyymmdd(bas_dd),
        "upserted_disclosures": count,
    }


def sync_shareholder_data(conn: psycopg.Connection, bas_dd: date) -> Dict[str, Any]:
    dart = DARTClient(DART_API_KEY)
    companies = fetch_active_companies(conn, bas_dd)

    raw_count = 0
    rebuilt_count = 0

    for company in companies:
        corp_code = company["dart_corp_code"]
        if not corp_code:
            continue

        try:
            rows = dart.fetch_majorstock(corp_code)
        except Exception:
            continue

        for row in rows:
            upsert_shareholder_filing_raw(conn, str(company["id"]), row)
            raw_count += 1

        rebuild_provisional_key_shareholder_latest(conn, company)
        rebuilt_count += 1

    return {
        "upserted_shareholder_raw": raw_count,
        "rebuilt_company_count": rebuilt_count,
    }


def purge_expired_companies(conn: psycopg.Connection, as_of: date) -> Dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("select public.purge_expired_companies(%s) as deleted_count", (as_of,))
        deleted_count = cur.fetchone()["deleted_count"]

    return {
        "as_of": yyyymmdd(as_of),
        "deleted_companies": deleted_count,
    }


# =========================================================
# runner
# =========================================================

def run_job(job_name: str, bas_dd: date) -> None:
    sync_run_id = start_sync_run(job_name, bas_dd)
    stats: Dict[str, Any] = {}

    try:
        with get_conn(autocommit=False) as conn:
            if job_name == "bootstrap":
                stats["seed_recent_universe"] = seed_recent_universe(conn, bas_dd)
                stats["sync_daily_prices"] = sync_daily_prices(conn, bas_dd)
                stats["sync_recent_disclosures"] = sync_recent_disclosures(conn, bas_dd, lookback_days=30)
                stats["sync_shareholder_data"] = sync_shareholder_data(conn, bas_dd)
                stats["purge_expired_companies"] = purge_expired_companies(conn, bas_dd)
                conn.commit()

            elif job_name == "daily":
                stats["seed_recent_universe"] = seed_recent_universe(conn, bas_dd)
                stats["sync_daily_prices"] = sync_daily_prices(conn, bas_dd)
                stats["sync_recent_disclosures"] = sync_recent_disclosures(conn, bas_dd, lookback_days=7)
                stats["sync_shareholder_data"] = sync_shareholder_data(conn, bas_dd)
                stats["purge_expired_companies"] = purge_expired_companies(conn, bas_dd)
                conn.commit()

            elif job_name == "purge":
                stats["purge_expired_companies"] = purge_expired_companies(conn, bas_dd)
                conn.commit()

            else:
                raise ValueError(f"Unknown job: {job_name}")

        finish_sync_run(sync_run_id, "SUCCESS", stats)
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    except Exception as e:
        finish_sync_run(sync_run_id, "FAILED", stats, error_message=str(e))
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job", choices=["bootstrap", "daily", "purge"])
    parser.add_argument("--date", dest="run_date", help="기준일 YYYYMMDD. 없으면 직전 영업일 사용")
    args = parser.parse_args()

    bas_dd = parse_yyyymmdd(args.run_date) if args.run_date else previous_business_day()
    if bas_dd is None:
        raise ValueError("--date 는 YYYYMMDD 형식이어야 합니다.")

    run_job(args.job, bas_dd)


if __name__ == "__main__":
    main()
