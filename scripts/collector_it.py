from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

import psycopg
import requests
from dotenv import load_dotenv
from psycopg.rows import dict_row


# =========================================================
# env
# =========================================================

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=False)
load_dotenv(BASE_DIR / ".env.local", override=False)
load_dotenv(override=False)

DATABASE_URL = os.getenv("DATABASE_URL")
KRX_AUTH_KEY = os.getenv("KRX_AUTH_KEY")
DART_API_KEY = os.getenv("DART_API_KEY")
KRX_API_BASE = os.getenv("KRX_API_BASE", "https://data-dbg.krx.co.kr/svc/apis/sto")
DART_API_BASE = os.getenv("DART_API_BASE", "https://opendart.fss.or.kr/api")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
REQUEST_RETRIES = int(os.getenv("REQUEST_RETRIES", "3"))
DEFAULT_IPO_WINDOW_DAYS = int(os.getenv("IPO_WINDOW_DAYS", "120"))
KST = ZoneInfo("Asia/Seoul")
TRACK_MARKETS = ("KOSPI", "KOSDAQ")


# =========================================================
# errors / logging
# =========================================================


class CollectorError(RuntimeError):
    pass


class DatabaseError(CollectorError):
    pass


class KRXAPIError(CollectorError):
    pass


class DARTAPIError(CollectorError):
    pass


# =========================================================
# utils
# =========================================================


def log(*args: Any, verbose: bool = False) -> None:
    if verbose:
        print(*args, file=sys.stderr)


json_scalar_types = (date, datetime, Decimal)


def json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Cannot JSON serialize: {type(value)}")


def yyyymmdd(d: date) -> str:
    return d.strftime("%Y%m%d")


def parse_krx_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw == "-":
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 8:
        try:
            return datetime.strptime(digits, "%Y%m%d").date()
        except ValueError:
            return None
    return None


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_stock_code(value: Any) -> Optional[str]:
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return None
    if len(digits) > 6:
        digits = digits[-6:]
    return digits.zfill(6)


def normalize_standard_code(value: Any) -> str:
    return normalize_text(value)


def kst_now() -> datetime:
    return datetime.now(KST)


def kst_today() -> date:
    return kst_now().date()


def normalize_holder_key(value: Any) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", normalize_text(value).lower())


def to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    raw = str(value).strip().replace(",", "")
    if not raw or raw == "-":
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def to_int(value: Any) -> Optional[int]:
    parsed = to_decimal(value)
    return int(parsed) if parsed is not None else None


def quant_pct(value: Optional[Decimal]) -> Optional[Decimal]:
    if value is None:
        return None
    return value.quantize(Decimal("0.0001"))


def safe_pct(value: Optional[Decimal]) -> Decimal:
    return quant_pct(value) or Decimal("0")


def calculate_return_since_ipo(offering_price: Optional[Decimal], close_price: Optional[Decimal]) -> Optional[Decimal]:
    if offering_price is None or close_price is None or offering_price == 0:
        return None
    return ((close_price - offering_price) / offering_price * Decimal("100")).quantize(Decimal("0.01"))


def previous_business_day(ref: Optional[date] = None) -> date:
    cur = ref or kst_today()
    cur -= timedelta(days=1)
    while cur.weekday() >= 5:
        cur -= timedelta(days=1)
    return cur


def business_days_back(end_date: date, days: int) -> list[date]:
    if days <= 0:
        return []
    out: list[date] = []
    cur = end_date
    while len(out) < days:
        if cur.weekday() < 5:
            out.append(cur)
        cur -= timedelta(days=1)
    out.sort()
    return out


def iso(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value else None


def ensure_env(*, require_db: bool = True, require_krx: bool = True, require_dart: bool = True) -> None:
    if require_db and not DATABASE_URL:
        raise CollectorError("DATABASE_URL 환경변수가 필요합니다.")
    if require_krx and not KRX_AUTH_KEY:
        raise CollectorError("KRX_AUTH_KEY 환경변수가 필요합니다.")
    if require_dart and not DART_API_KEY:
        raise CollectorError("DART_API_KEY 환경변수가 필요합니다.")


# =========================================================
# dataclasses
# =========================================================


@dataclass(frozen=True)
class BaseInfoRow:
    standard_code: str
    stock_code: str
    company_name: str
    company_name_eng: Optional[str]
    listing_date: date
    market_type: str
    security_group: Optional[str]
    stock_cert_type: Optional[str]
    sector_name: Optional[str]
    par_value: Optional[Decimal]
    listed_shares: Optional[int]
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class TradeRow:
    stock_code: str
    trade_date: date
    open_price: Optional[Decimal]
    high_price: Optional[Decimal]
    low_price: Optional[Decimal]
    close_price: Optional[Decimal]
    volume: Optional[int]
    trade_value: Optional[Decimal]
    market_cap: Optional[Decimal]
    shares_outstanding: Optional[int]


@dataclass(frozen=True)
class ShareholderRawRow:
    company_id: str
    rcept_no: str
    dart_corp_code: str
    corp_name: str
    rcept_dt: date
    report_tp: str
    repror: str
    stkqy: Optional[Decimal]
    stkqy_irds: Optional[Decimal]
    stkrt: Optional[Decimal]
    stkrt_irds: Optional[Decimal]
    ctr_stkqy: Optional[Decimal]
    ctr_stkrt: Optional[Decimal]
    report_resn: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class ShareholderLatestRow:
    holder_key: str
    holder_name: str
    holder_role: Optional[str]
    ipo_base_pct: Decimal
    latest_pct: Decimal
    change_pct: Decimal
    ipo_snapshot_date: Optional[date]
    latest_snapshot_date: Optional[date]
    latest_rcept_no: Optional[str]
    is_new_holder: bool
    is_exited_holder: bool


@dataclass(frozen=True)
class MarketResolver:
    standard_to_short: dict[str, str]
    name_to_short: dict[str, str]


@dataclass(frozen=True)
class Context:
    bas_dd: date
    dry_run: bool
    verbose: bool
    krx: "KRXClient"
    dart: "DARTClient"
    ipo_window_days: int


# =========================================================
# HTTP clients
# =========================================================


class BaseHTTPClient:
    def __init__(self, timeout: int = REQUEST_TIMEOUT, retries: int = REQUEST_RETRIES) -> None:
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()

    def get(self, url: str, *, params: Optional[dict[str, Any]] = None, headers: Optional[dict[str, str]] = None) -> requests.Response:
        last_error: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                return response
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == self.retries:
                    break
                time.sleep(min(2 ** (attempt - 1), 5))
        raise CollectorError(f"HTTP 요청 실패: {url} / {last_error}")


class KRXClient(BaseHTTPClient):
    def __init__(self, auth_key: str, api_base: str) -> None:
        super().__init__()
        self.auth_key = auth_key
        self.api_base = api_base.rstrip("/")

    def _get(self, endpoint: str, *, bas_dd: date) -> list[dict[str, Any]]:
        url = f"{self.api_base}/{endpoint}"
        response = self.get(url, params={"basDd": yyyymmdd(bas_dd)}, headers={"AUTH_KEY": self.auth_key})
        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise KRXAPIError(f"KRX JSON 파싱 실패: {endpoint}") from exc

        if isinstance(payload, dict):
            rows = payload.get("OutBlock_1") or []
        elif isinstance(payload, list):
            rows = payload
        else:
            rows = []

        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    def fetch_base_info(self, market: str, *, bas_dd: date) -> list[BaseInfoRow]:
        endpoint = "stk_isu_base_info" if market == "KOSPI" else "ksq_isu_base_info"
        rows = self._get(endpoint, bas_dd=bas_dd)
        out: list[BaseInfoRow] = []
        for row in rows:
            stock_code = normalize_stock_code(row.get("ISU_SRT_CD"))
            standard_code = normalize_standard_code(row.get("ISU_CD"))
            listing_date = parse_krx_date(row.get("LIST_DD"))
            if not stock_code or not listing_date:
                continue
            company_name = normalize_text(row.get("ISU_ABBRV") or row.get("ISU_NM"))
            if not company_name:
                continue
            out.append(
                BaseInfoRow(
                    standard_code=standard_code,
                    stock_code=stock_code,
                    company_name=company_name,
                    company_name_eng=normalize_text(row.get("ISU_ENG_NM")) or None,
                    listing_date=listing_date,
                    market_type=market,
                    security_group=normalize_text(row.get("SECUGRP_NM")) or None,
                    stock_cert_type=normalize_text(row.get("KIND_STKCERT_TP_NM")) or None,
                    sector_name=normalize_text(row.get("SECT_TP_NM")) or None,
                    par_value=to_decimal(row.get("PARVAL")),
                    listed_shares=to_int(row.get("LIST_SHRS")),
                    raw_payload=row,
                )
            )
        return out

    def build_market_resolver(self, base_rows: Iterable[BaseInfoRow]) -> MarketResolver:
        standard_to_short: dict[str, str] = {}
        name_to_short: dict[str, str] = {}
        for row in base_rows:
            if row.standard_code:
                standard_to_short[row.standard_code] = row.stock_code
            name_to_short[normalize_text(row.company_name)] = row.stock_code
        return MarketResolver(standard_to_short=standard_to_short, name_to_short=name_to_short)

    def fetch_daily_trade(self, market: str, *, bas_dd: date, resolver: MarketResolver) -> list[TradeRow]:
        endpoint = "stk_bydd_trd" if market == "KOSPI" else "ksq_bydd_trd"
        rows = self._get(endpoint, bas_dd=bas_dd)
        out: list[TradeRow] = []
        for row in rows:
            stock_code = self._resolve_trade_stock_code(row, resolver)
            if not stock_code:
                continue
            trade_date = parse_krx_date(row.get("BAS_DD")) or bas_dd
            out.append(
                TradeRow(
                    stock_code=stock_code,
                    trade_date=trade_date,
                    open_price=to_decimal(row.get("TDD_OPNPRC")),
                    high_price=to_decimal(row.get("TDD_HGPRC")),
                    low_price=to_decimal(row.get("TDD_LWPRC")),
                    close_price=to_decimal(row.get("TDD_CLSPRC")),
                    volume=to_int(row.get("ACC_TRDVOL")),
                    trade_value=to_decimal(row.get("ACC_TRDVAL")),
                    market_cap=to_decimal(row.get("MKTCAP")),
                    shares_outstanding=to_int(row.get("LIST_SHRS")),
                )
            )
        return out

    def _resolve_trade_stock_code(self, row: dict[str, Any], resolver: MarketResolver) -> Optional[str]:
        direct_short = normalize_stock_code(row.get("ISU_SRT_CD"))
        if direct_short and len(direct_short) == 6:
            return direct_short

        raw_code_text = normalize_standard_code(row.get("ISU_CD"))
        if raw_code_text:
            mapped = resolver.standard_to_short.get(raw_code_text)
            if mapped:
                return mapped

        raw_digits = normalize_stock_code(row.get("ISU_CD"))
        if raw_digits and len(raw_digits) == 6:
            return raw_digits

        name = normalize_text(row.get("ISU_NM"))
        return resolver.name_to_short.get(name)


class DARTClient(BaseHTTPClient):
    def __init__(self, api_key: str, api_base: str) -> None:
        super().__init__(timeout=60)
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")

    def _get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.api_base}/{endpoint}"
        response = self.get(url, params={"crtfc_key": self.api_key, **params})
        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise DARTAPIError(f"DART JSON 파싱 실패: {endpoint}") from exc

        status = payload.get("status")
        if status in (None, "000", "013"):
            return payload
        raise DARTAPIError(f"DART 오류 {status}: {payload.get('message')}")

    def fetch_corp_code_map(self) -> dict[str, str]:
        url = f"{self.api_base}/corpCode.xml"
        response = self.get(url, params={"crtfc_key": self.api_key})
        try:
            archive = zipfile.ZipFile(BytesIO(response.content))
            xml_name = archive.namelist()[0]
            xml_bytes = archive.read(xml_name)
            root = ET.fromstring(xml_bytes)
        except Exception as exc:  # noqa: BLE001
            raise DARTAPIError("corpCode.xml 처리 실패") from exc

        out: dict[str, str] = {}
        for item in root.findall(".//list"):
            corp_code = normalize_text(item.findtext("corp_code"))
            stock_code = normalize_stock_code(item.findtext("stock_code"))
            if corp_code and stock_code:
                out[stock_code] = corp_code
        return out

    def fetch_company_info(self, corp_code: str) -> dict[str, Any]:
        return self._get_json("company.json", {"corp_code": corp_code})

    def fetch_disclosures(self, corp_code: str, *, start_date: date, end_date: date) -> list[dict[str, Any]]:
        page_no = 1
        out: list[dict[str, Any]] = []
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
            rows = payload.get("list") or []
            out.extend([row for row in rows if isinstance(row, dict)])
            total_page = int(payload.get("total_page") or 1)
            if page_no >= total_page:
                break
            page_no += 1
        return out

    def fetch_majorstock(self, corp_code: str) -> list[dict[str, Any]]:
        payload = self._get_json("majorstock.json", {"corp_code": corp_code})
        return [row for row in (payload.get("list") or []) if isinstance(row, dict)]

    def fetch_offering_terms(self, corp_code: str, *, listing_date: date) -> dict[str, Any]:
        # best-effort only. empty dict when unavailable.
        try:
            payload = self._get_json(
                "estkRs.json",
                {
                    "corp_code": corp_code,
                    "bgn_de": yyyymmdd(listing_date - timedelta(days=365)),
                    "end_de": yyyymmdd(listing_date + timedelta(days=60)),
                },
            )
        except DARTAPIError:
            return {}

        group_rows: list[dict[str, Any]] = []
        for group in payload.get("group") or []:
            if not isinstance(group, dict):
                continue
            for row in group.get("list") or []:
                if isinstance(row, dict):
                    group_rows.append(row)
        if not group_rows:
            return {}

        group_rows.sort(key=lambda row: normalize_text(row.get("rcept_no")), reverse=True)
        target = group_rows[0]
        return {
            "offering_price": to_decimal(target.get("slprc")),
            "offering_amount": to_decimal(target.get("slta")),
            "par_value": to_decimal(target.get("fv")),
            "source_rcept_no": normalize_text(target.get("rcept_no")) or None,
        }


# =========================================================
# DB helpers
# =========================================================

REQUIRED_TABLES = {
    "companies",
    "price_daily",
    "disclosures",
    "shareholder_filings_raw",
    "key_shareholder_latest",
    "sync_runs",
}
OPTIONAL_TABLES = {"company_archive_log"}


def get_conn(autocommit: bool = False) -> psycopg.Connection:
    ensure_env(require_db=True, require_krx=False, require_dart=False)
    conn = psycopg.connect(DATABASE_URL, autocommit=autocommit, row_factory=dict_row)
    with conn.cursor() as cur:
        cur.execute("set time zone 'Asia/Seoul'")
    return conn


def existing_tables(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select table_name
            from information_schema.tables
            where table_schema = 'public'
            """
        )
        return {row["table_name"] for row in cur.fetchall()}


def verify_required_tables(conn: psycopg.Connection) -> None:
    tables = existing_tables(conn)
    missing = sorted(REQUIRED_TABLES - tables)
    if missing:
        raise DatabaseError(f"필수 테이블이 없습니다: {', '.join(missing)}")


def has_archive_table(conn: psycopg.Connection) -> bool:
    return "company_archive_log" in existing_tables(conn)


def start_sync_run(conn: psycopg.Connection, *, job_name: str, run_date: date) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into public.sync_runs (job_name, run_date, status, started_at)
            values (%s, %s, 'RUNNING', %s)
            returning id
            """,
            (job_name, run_date, kst_now()),
        )
        return int(cur.fetchone()["id"])


def finish_sync_run(conn: psycopg.Connection, *, sync_run_id: int, status: str, stats: dict[str, Any], error_message: Optional[str] = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            update public.sync_runs
            set status = %s,
                finished_at = %s,
                stats = %s,
                error_message = %s
            where id = %s
            """,
            (status, kst_now(), json.dumps(stats, ensure_ascii=False, default=json_default), error_message, sync_run_id),
        )


def fetch_existing_stock_codes(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("select stock_code from public.companies")
        return {str(row["stock_code"]) for row in cur.fetchall()}


def fetch_active_companies(conn: psycopg.Connection, *, as_of: date, limit: Optional[int] = None) -> list[dict[str, Any]]:
    sql = (
        """
        select *
        from public.companies
        where is_active = true
          and tracking_expires_at >= %s
        order by listing_date desc, stock_code asc
        """
    )
    params: list[Any] = [as_of]
    if limit:
        sql += " limit %s"
        params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def fetch_company_by_stock_code(conn: psycopg.Connection, stock_code: str) -> Optional[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("select * from public.companies where stock_code = %s", (stock_code,))
        return cur.fetchone()


def fetch_expired_companies(conn: psycopg.Connection, *, as_of: date) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select id, stock_code, company_name, listing_date, tracking_expires_at
            from public.companies
            where tracking_expires_at < %s
            order by tracking_expires_at asc, stock_code asc
            """,
            (as_of,),
        )
        return list(cur.fetchall())


def upsert_company(conn: psycopg.Connection, payload: dict[str, Any]) -> None:
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
                latest_disclosure_date,
                key_shareholders_change_pct,
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
                %(latest_disclosure_date)s,
                %(key_shareholders_change_pct)s,
                %(is_active)s
            )
            on conflict (stock_code) do update
            set dart_corp_code = excluded.dart_corp_code,
                company_name = excluded.company_name,
                company_name_eng = coalesce(excluded.company_name_eng, public.companies.company_name_eng),
                market_type = excluded.market_type,
                security_group = coalesce(excluded.security_group, public.companies.security_group),
                sector_name = coalesce(excluded.sector_name, public.companies.sector_name),
                industry = coalesce(excluded.industry, public.companies.industry),
                listing_date = excluded.listing_date,
                tracking_started_at = least(public.companies.tracking_started_at, excluded.tracking_started_at),
                tracking_expires_at = excluded.tracking_expires_at,
                offering_price = coalesce(public.companies.offering_price, excluded.offering_price),
                offering_amount = coalesce(public.companies.offering_amount, excluded.offering_amount),
                offering_price_source = coalesce(public.companies.offering_price_source, excluded.offering_price_source),
                offering_price_source_rcept_no = coalesce(public.companies.offering_price_source_rcept_no, excluded.offering_price_source_rcept_no),
                par_value = coalesce(excluded.par_value, public.companies.par_value),
                listed_shares = coalesce(excluded.listed_shares, public.companies.listed_shares),
                homepage_url = coalesce(excluded.homepage_url, public.companies.homepage_url),
                ir_url = coalesce(excluded.ir_url, public.companies.ir_url),
                is_active = true
            """,
            payload,
        )


def upsert_price_daily(conn: psycopg.Connection, *, company_id: str, row: TradeRow) -> None:
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
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'KRX_OPEN_API', null)
            on conflict (company_id, trade_date) do update
            set open_price = excluded.open_price,
                high_price = excluded.high_price,
                low_price = excluded.low_price,
                close_price = excluded.close_price,
                volume = excluded.volume,
                trade_value = excluded.trade_value,
                market_cap = excluded.market_cap,
                shares_outstanding = excluded.shares_outstanding,
                source = excluded.source,
                raw_payload = null
            """,
            (
                company_id,
                row.trade_date,
                row.open_price,
                row.high_price,
                row.low_price,
                row.close_price,
                row.volume,
                row.trade_value,
                row.market_cap,
                row.shares_outstanding,
            ),
        )


def update_company_price_snapshot(
    conn: psycopg.Connection,
    *,
    company_id: str,
    current_price: Optional[Decimal],
    current_price_date: Optional[date],
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
            (current_price, current_price_date, return_since_ipo, company_id),
        )


def upsert_disclosure(conn: psycopg.Connection, payload: dict[str, Any]) -> None:
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
            values (
                %(rcept_no)s,
                %(company_id)s,
                %(dart_corp_code)s,
                %(stock_code)s,
                %(rcept_dt)s,
                %(report_nm)s,
                %(pblntf_ty)s,
                %(pblntf_detail_ty)s,
                %(corp_cls)s,
                %(flr_nm)s,
                %(rm)s,
                %(disclosure_url)s,
                %(is_shareholder_related)s,
                null
            )
            on conflict (rcept_no) do update
            set company_id = excluded.company_id,
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
                raw_payload = null
            """,
            payload,
        )


def update_company_latest_disclosure_date(conn: psycopg.Connection, *, company_id: str, latest_date: Optional[date]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "update public.companies set latest_disclosure_date = %s where id = %s",
            (latest_date, company_id),
        )


def upsert_shareholder_raw(conn: psycopg.Connection, row: ShareholderRawRow) -> None:
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
            set dart_corp_code = excluded.dart_corp_code,
                corp_name = excluded.corp_name,
                rcept_dt = excluded.rcept_dt,
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
                row.company_id,
                row.rcept_no,
                row.dart_corp_code,
                row.corp_name,
                row.rcept_dt,
                row.report_tp,
                row.repror,
                row.stkqy,
                row.stkqy_irds,
                row.stkrt,
                row.stkrt_irds,
                row.ctr_stkqy,
                row.ctr_stkrt,
                row.report_resn,
                json.dumps(row.raw_payload, ensure_ascii=False, default=json_default),
            ),
        )


def fetch_shareholder_raw_for_company(conn: psycopg.Connection, *, company_id: str) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select *
            from public.shareholder_filings_raw
            where company_id = %s
            order by rcept_dt asc, rcept_no asc, repror asc
            """,
            (company_id,),
        )
        return list(cur.fetchall())


def replace_key_shareholder_latest(conn: psycopg.Connection, *, company_id: str, rows: list[ShareholderLatestRow]) -> None:
    with conn.cursor() as cur:
        cur.execute("delete from public.key_shareholder_latest where company_id = %s", (company_id,))
        for row in rows:
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
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PROVISIONAL_DART_MAJORSTOCK', null)
                """,
                (
                    company_id,
                    row.holder_key,
                    row.holder_name,
                    row.holder_role,
                    row.ipo_base_pct,
                    row.latest_pct,
                    row.change_pct,
                    row.ipo_snapshot_date,
                    row.latest_snapshot_date,
                    row.latest_rcept_no,
                    row.is_new_holder,
                    row.is_exited_holder,
                ),
            )


def update_company_shareholder_change(conn: psycopg.Connection, *, company_id: str, total_change_pct: Decimal) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "update public.companies set key_shareholders_change_pct = %s where id = %s",
            (total_change_pct, company_id),
        )


def archive_and_delete_company(conn: psycopg.Connection, *, company: dict[str, Any], deleted_on: date, reason: str = "TRACKING_EXPIRED") -> None:
    if has_archive_table(conn):
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.company_archive_log (
                    original_company_id,
                    stock_code,
                    company_name,
                    listing_date,
                    tracking_expires_at,
                    db_deleted_at,
                    reason
                )
                values (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    company["id"],
                    company["stock_code"],
                    company["company_name"],
                    company["listing_date"],
                    company["tracking_expires_at"],
                    deleted_on,
                    reason,
                ),
            )
    with conn.cursor() as cur:
        cur.execute("delete from public.companies where id = %s", (company["id"],))


# =========================================================
# domain mapping helpers
# =========================================================


def should_keep_base_row(row: BaseInfoRow) -> bool:
    if row.market_type not in TRACK_MARKETS:
        return False

    group = normalize_text(row.security_group)
    stock_kind = normalize_text(row.stock_cert_type)
    sector = normalize_text(row.sector_name)
    company_name = normalize_text(row.company_name)

    group_upper = group.upper()
    stock_kind_upper = stock_kind.upper()
    sector_upper = sector.upper()
    company_upper = company_name.upper()

    # KIND 화면 기준으로 코스피/코스닥의 신규상장 + 일반주권만 추적한다.
    # KRX에서는 SECUGRP_NM(증권구분), KIND_STKCERT_TP_NM(주식종류)을 활용해 보수적으로 필터링한다.
    if group and "주권" not in group:
        return False

    blocked_group_keywords = [
        "외국",
        "선박투자",
        "수익증권",
        "리츠",
        "인프라",
        "ETF",
        "ETN",
        "ELW",
        "신주인수권",
        "전환사채",
        "교환사채",
        "파생",
    ]
    if any(keyword in group_upper for keyword in blocked_group_keywords):
        return False

    blocked_stock_kind_keywords = [
        "우선",
        "전환",
        "상환",
        "신주인수권",
        "종류주",
    ]
    if any(keyword in stock_kind_upper for keyword in blocked_stock_kind_keywords):
        return False

    # 스팩 제외
    if "SPAC" in sector_upper or "SPAC" in company_upper or "스팩" in company_name:
        return False

    return True


def is_shareholder_related_report(report_nm: str) -> bool:
    keywords = [
        "대량보유",
        "주식등의대량보유상황보고서",
        "임원ㆍ주요주주특정증권등소유상황보고서",
        "주요사항보고서",
        "최대주주",
        "주식소유",
        "소유상황",
    ]
    return any(keyword in normalize_text(report_nm) for keyword in keywords)


def build_disclosure_url(rcept_no: str) -> str:
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={quote(rcept_no)}"


def map_company_payload(
    *,
    base_row: BaseInfoRow,
    corp_code: Optional[str],
    company_info: dict[str, Any],
    offering_info: dict[str, Any],
    current_price: Optional[Decimal],
    current_price_date: Optional[date],
) -> dict[str, Any]:
    offering_price = offering_info.get("offering_price")
    offering_amount = offering_info.get("offering_amount")
    return_since_ipo = calculate_return_since_ipo(offering_price, current_price)

    industry = normalize_text(company_info.get("induty_nm") or company_info.get("induty_code") or "") or None
    homepage_url = normalize_text(company_info.get("hm_url")) or None
    ir_url = normalize_text(company_info.get("ir_url")) or None

    return {
        "stock_code": base_row.stock_code,
        "dart_corp_code": corp_code,
        "company_name": base_row.company_name,
        "company_name_eng": base_row.company_name_eng,
        "market_type": base_row.market_type,
        "security_group": base_row.security_group,
        "sector_name": base_row.sector_name,
        "industry": industry,
        "listing_date": base_row.listing_date,
        "tracking_started_at": kst_today(),
        "tracking_expires_at": base_row.listing_date + timedelta(days=365 * 3),
        "offering_price": offering_price,
        "offering_amount": offering_amount,
        "offering_price_source": "DART_ESTKRS" if offering_price is not None else None,
        "offering_price_source_rcept_no": offering_info.get("source_rcept_no"),
        "par_value": base_row.par_value or offering_info.get("par_value"),
        "listed_shares": base_row.listed_shares,
        "homepage_url": homepage_url,
        "ir_url": ir_url,
        "current_price": current_price,
        "current_price_date": current_price_date,
        "return_since_ipo": return_since_ipo,
        "latest_disclosure_date": None,
        "key_shareholders_change_pct": Decimal("0"),
        "is_active": True,
    }


def map_disclosure_payload(*, company: dict[str, Any], row: dict[str, Any]) -> Optional[dict[str, Any]]:
    rcept_no = normalize_text(row.get("rcept_no"))
    rcept_dt = parse_krx_date(row.get("rcept_dt"))
    report_nm = normalize_text(row.get("report_nm"))
    if not rcept_no or not rcept_dt or not report_nm:
        return None
    return {
        "rcept_no": rcept_no,
        "company_id": company["id"],
        "dart_corp_code": company.get("dart_corp_code"),
        "stock_code": company["stock_code"],
        "rcept_dt": rcept_dt,
        "report_nm": report_nm,
        "pblntf_ty": normalize_text(row.get("pblntf_ty")) or None,
        "pblntf_detail_ty": normalize_text(row.get("pblntf_detail_ty")) or None,
        "corp_cls": normalize_text(row.get("corp_cls")) or None,
        "flr_nm": normalize_text(row.get("flr_nm")) or None,
        "rm": normalize_text(row.get("rm")) or None,
        "disclosure_url": build_disclosure_url(rcept_no),
        "is_shareholder_related": is_shareholder_related_report(report_nm),
    }


def map_shareholder_raw(*, company: dict[str, Any], row: dict[str, Any]) -> Optional[ShareholderRawRow]:
    rcept_no = normalize_text(row.get("rcept_no"))
    repror = normalize_text(row.get("repror"))
    rcept_dt = parse_krx_date(row.get("rcept_dt"))
    if not rcept_no or not repror or not rcept_dt:
        return None
    return ShareholderRawRow(
        company_id=str(company["id"]),
        rcept_no=rcept_no,
        dart_corp_code=normalize_text(company.get("dart_corp_code")),
        corp_name=normalize_text(row.get("corp_name") or company["company_name"]),
        rcept_dt=rcept_dt,
        report_tp=normalize_text(row.get("report_tp")),
        repror=repror,
        stkqy=to_decimal(row.get("stkqy")),
        stkqy_irds=to_decimal(row.get("stkqy_irds")),
        stkrt=quant_pct(to_decimal(row.get("stkrt"))),
        stkrt_irds=quant_pct(to_decimal(row.get("stkrt_irds"))),
        ctr_stkqy=to_decimal(row.get("ctr_stkqy")),
        ctr_stkrt=quant_pct(to_decimal(row.get("ctr_stkrt"))),
        report_resn=normalize_text(row.get("report_resn")),
        raw_payload=row,
    )


def build_latest_shareholder_rows(*, company: dict[str, Any], raw_rows: list[dict[str, Any]], ipo_window_days: int) -> list[ShareholderLatestRow]:
    if not raw_rows:
        return []

    listing_date: date = company["listing_date"]
    ipo_window_end = listing_date + timedelta(days=ipo_window_days)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in raw_rows:
        holder_name = normalize_text(row.get("repror"))
        holder_key = normalize_holder_key(holder_name)
        if not holder_key:
            continue
        grouped.setdefault(holder_key, []).append(row)

    out: list[ShareholderLatestRow] = []
    for holder_key, rows in grouped.items():
        rows.sort(key=lambda x: (x.get("rcept_dt"), x.get("rcept_no"), x.get("repror")))
        first_row = rows[0]
        latest_row = rows[-1]

        first_dt = first_row.get("rcept_dt")
        latest_dt = latest_row.get("rcept_dt")
        first_pct = quant_pct(first_row.get("stkrt")) or Decimal("0")
        latest_pct = quant_pct(latest_row.get("stkrt")) or Decimal("0")
        holder_name = normalize_text(latest_row.get("repror") or first_row.get("repror"))
        holder_role = normalize_text(latest_row.get("report_tp") or first_row.get("report_tp")) or None

        is_new_holder = not (first_dt and first_dt <= ipo_window_end)
        ipo_base_pct = Decimal("0") if is_new_holder else first_pct
        change_pct = quant_pct(latest_pct - ipo_base_pct) or Decimal("0")
        is_exited_holder = latest_pct == 0 and ipo_base_pct > 0

        out.append(
            ShareholderLatestRow(
                holder_key=holder_key,
                holder_name=holder_name,
                holder_role=holder_role,
                ipo_base_pct=ipo_base_pct,
                latest_pct=latest_pct,
                change_pct=change_pct,
                ipo_snapshot_date=first_dt if not is_new_holder else None,
                latest_snapshot_date=latest_dt,
                latest_rcept_no=normalize_text(latest_row.get("rcept_no")) or None,
                is_new_holder=is_new_holder,
                is_exited_holder=is_exited_holder,
            )
        )

    out.sort(key=lambda row: (row.holder_name, row.holder_key))
    return out


# =========================================================
# business logic
# =========================================================


def collect_recent_base_candidates(
    ctx: Context,
    *,
    listing_start_date: date,
    listing_end_date: date,
) -> tuple[list[BaseInfoRow], dict[str, TradeRow], dict[str, str], dict[str, list[BaseInfoRow]]]:
    corp_code_map = ctx.dart.fetch_corp_code_map()
    candidates: list[BaseInfoRow] = []
    trade_map: dict[str, TradeRow] = {}
    base_rows_by_market: dict[str, list[BaseInfoRow]] = {}

    for market in TRACK_MARKETS:
        base_rows = [row for row in ctx.krx.fetch_base_info(market, bas_dd=ctx.bas_dd) if should_keep_base_row(row)]
        base_rows_by_market[market] = base_rows
        resolver = ctx.krx.build_market_resolver(base_rows)
        trades = ctx.krx.fetch_daily_trade(market, bas_dd=ctx.bas_dd, resolver=resolver)
        for trade in trades:
            trade_map[trade.stock_code] = trade
        selected = [row for row in base_rows if listing_start_date <= row.listing_date <= listing_end_date]
        candidates.extend(selected)
        log(f"[KRX] {market} base_rows={len(base_rows)} selected={len(selected)} trades={len(trades)}", verbose=ctx.verbose)

    # Deduplicate by stock_code.
    deduped: dict[str, BaseInfoRow] = {}
    for row in candidates:
        deduped[row.stock_code] = row

    # Corp code map is returned separately.
    log(f"[DART] corp_code_map={len(corp_code_map)}", verbose=ctx.verbose)
    return list(deduped.values()), trade_map, corp_code_map, base_rows_by_market


def seed_recent_universe(conn: psycopg.Connection, ctx: Context, *, limit: Optional[int] = None) -> dict[str, Any]:
    seed_cutoff = ctx.bas_dd - timedelta(days=365)
    candidates, trade_map, corp_code_map, _ = collect_recent_base_candidates(
        ctx,
        listing_start_date=seed_cutoff,
        listing_end_date=ctx.bas_dd,
    )
    candidates.sort(key=lambda row: (row.listing_date, row.stock_code), reverse=True)
    if limit:
        candidates = candidates[:limit]

    existing = fetch_existing_stock_codes(conn)
    upserted = 0
    sample_codes: list[str] = []

    for base_row in candidates:
        corp_code = corp_code_map.get(base_row.stock_code)
        company_info = ctx.dart.fetch_company_info(corp_code) if corp_code else {}
        offering_info = ctx.dart.fetch_offering_terms(corp_code, listing_date=base_row.listing_date) if corp_code else {}
        trade = trade_map.get(base_row.stock_code)
        payload = map_company_payload(
            base_row=base_row,
            corp_code=corp_code,
            company_info=company_info,
            offering_info=offering_info,
            current_price=trade.close_price if trade else None,
            current_price_date=trade.trade_date if trade else None,
        )
        if base_row.stock_code not in existing:
            upserted += 1
            sample_codes.append(base_row.stock_code)
        if not ctx.dry_run:
            upsert_company(conn, payload)
        existing.add(base_row.stock_code)

    return {
        "mode": "initial_seed",
        "seed_cutoff": iso(seed_cutoff),
        "eligible_companies": len(candidates),
        "upserted_companies": upserted,
        "sample_stock_codes": sample_codes[:10],
    }


def add_new_listings(conn: psycopg.Connection, ctx: Context, *, lookback_days: int) -> dict[str, Any]:
    start_date = ctx.bas_dd - timedelta(days=max(1, lookback_days))
    candidates, trade_map, corp_code_map, _ = collect_recent_base_candidates(
        ctx,
        listing_start_date=start_date,
        listing_end_date=ctx.bas_dd,
    )
    existing = fetch_existing_stock_codes(conn)
    new_rows = [row for row in candidates if row.stock_code not in existing]
    inserted_codes: list[str] = []

    for base_row in new_rows:
        corp_code = corp_code_map.get(base_row.stock_code)
        company_info = ctx.dart.fetch_company_info(corp_code) if corp_code else {}
        offering_info = ctx.dart.fetch_offering_terms(corp_code, listing_date=base_row.listing_date) if corp_code else {}
        trade = trade_map.get(base_row.stock_code)
        payload = map_company_payload(
            base_row=base_row,
            corp_code=corp_code,
            company_info=company_info,
            offering_info=offering_info,
            current_price=trade.close_price if trade else None,
            current_price_date=trade.trade_date if trade else None,
        )
        inserted_codes.append(base_row.stock_code)
        if not ctx.dry_run:
            upsert_company(conn, payload)

    return {
        "mode": "daily_new_listing_check",
        "lookback_start": iso(start_date),
        "lookback_end": iso(ctx.bas_dd),
        "detected_new_companies": len(new_rows),
        "sample_stock_codes": inserted_codes[:10],
    }


def sync_prices(conn: psycopg.Connection, ctx: Context, *, price_days: int, limit: Optional[int] = None) -> dict[str, Any]:
    companies = fetch_active_companies(conn, as_of=ctx.bas_dd, limit=limit)
    if not companies:
        return {"companies": 0, "price_rows": 0, "updated_snapshots": 0}

    dates = business_days_back(ctx.bas_dd, price_days)
    if not dates:
        return {"companies": len(companies), "price_rows": 0, "updated_snapshots": 0}

    market_groups = {market: [] for market in TRACK_MARKETS}
    for company in companies:
        market_groups[company["market_type"]].append(company)

    all_trade_maps: dict[tuple[str, date], dict[str, TradeRow]] = {}
    for market, companies_in_market in market_groups.items():
        if not companies_in_market:
            continue
        base_rows = [row for row in ctx.krx.fetch_base_info(market, bas_dd=ctx.bas_dd) if should_keep_base_row(row)]
        resolver = ctx.krx.build_market_resolver(base_rows)
        for d in dates:
            trades = ctx.krx.fetch_daily_trade(market, bas_dd=d, resolver=resolver)
            mapped = {row.stock_code: row for row in trades}
            all_trade_maps[(market, d)] = mapped
            log(f"[PRICES] {market} {d.isoformat()} rows={len(mapped)}", verbose=ctx.verbose)

    price_rows = 0
    updated_snapshots = 0

    for company in companies:
        latest_trade: Optional[TradeRow] = None
        for d in dates:
            trade = all_trade_maps.get((company["market_type"], d), {}).get(company["stock_code"])
            if not trade:
                continue
            price_rows += 1
            if latest_trade is None or trade.trade_date > latest_trade.trade_date:
                latest_trade = trade
            if not ctx.dry_run:
                upsert_price_daily(conn, company_id=str(company["id"]), row=trade)
        if latest_trade:
            updated_snapshots += 1
            return_since_ipo = calculate_return_since_ipo(company.get("offering_price"), latest_trade.close_price)
            if not ctx.dry_run:
                update_company_price_snapshot(
                    conn,
                    company_id=str(company["id"]),
                    current_price=latest_trade.close_price,
                    current_price_date=latest_trade.trade_date,
                    return_since_ipo=return_since_ipo,
                )

    return {
        "companies": len(companies),
        "price_days": len(dates),
        "price_rows": price_rows,
        "updated_snapshots": updated_snapshots,
    }


def sync_disclosures(conn: psycopg.Connection, ctx: Context, *, disclosure_days: int, limit: Optional[int] = None) -> dict[str, Any]:
    companies = fetch_active_companies(conn, as_of=ctx.bas_dd, limit=limit)
    start_date = ctx.bas_dd - timedelta(days=max(1, disclosure_days))
    total_rows = 0
    updated_companies = 0

    for company in companies:
        corp_code = company.get("dart_corp_code")
        if not corp_code:
            continue
        rows = ctx.dart.fetch_disclosures(corp_code, start_date=start_date, end_date=ctx.bas_dd)
        latest_dt: Optional[date] = None
        for row in rows:
            mapped = map_disclosure_payload(company=company, row=row)
            if not mapped:
                continue
            total_rows += 1
            if latest_dt is None or mapped["rcept_dt"] > latest_dt:
                latest_dt = mapped["rcept_dt"]
            if not ctx.dry_run:
                upsert_disclosure(conn, mapped)
        if rows:
            updated_companies += 1
            if not ctx.dry_run:
                update_company_latest_disclosure_date(conn, company_id=str(company["id"]), latest_date=latest_dt)

    return {
        "companies": len(companies),
        "start_date": iso(start_date),
        "end_date": iso(ctx.bas_dd),
        "disclosure_rows": total_rows,
        "companies_with_updates": updated_companies,
    }


def sync_shareholders(conn: psycopg.Connection, ctx: Context, *, limit: Optional[int] = None) -> dict[str, Any]:
    companies = fetch_active_companies(conn, as_of=ctx.bas_dd, limit=limit)
    raw_count = 0
    company_updates = 0

    for company in companies:
        corp_code = company.get("dart_corp_code")
        if not corp_code:
            continue
        raw_rows = ctx.dart.fetch_majorstock(corp_code)
        inserted_for_company = 0
        for row in raw_rows:
            mapped = map_shareholder_raw(company=company, row=row)
            if not mapped:
                continue
            raw_count += 1
            inserted_for_company += 1
            if not ctx.dry_run:
                upsert_shareholder_raw(conn, mapped)

        if inserted_for_company == 0:
            continue
        company_updates += 1
        if not ctx.dry_run:
            materialized_rows = fetch_shareholder_raw_for_company(conn, company_id=str(company["id"]))
            latest_rows = build_latest_shareholder_rows(company=company, raw_rows=materialized_rows, ipo_window_days=ctx.ipo_window_days)
            replace_key_shareholder_latest(conn, company_id=str(company["id"]), rows=latest_rows)
            total_change_pct = sum((row.change_pct for row in latest_rows), Decimal("0"))
            update_company_shareholder_change(conn, company_id=str(company["id"]), total_change_pct=quant_pct(total_change_pct) or Decimal("0"))

    return {
        "companies": len(companies),
        "raw_rows": raw_count,
        "companies_with_updates": company_updates,
    }


def purge_expired(conn: psycopg.Connection, ctx: Context) -> dict[str, Any]:
    expired = fetch_expired_companies(conn, as_of=ctx.bas_dd)
    archived = 0
    sample_codes: list[str] = []
    for company in expired:
        archived += 1
        sample_codes.append(company["stock_code"])
        if not ctx.dry_run:
            archive_and_delete_company(conn, company=company, deleted_on=ctx.bas_dd)
    return {
        "expired_companies": len(expired),
        "archived_companies": archived,
        "sample_stock_codes": sample_codes[:10],
        "archive_table_present": has_archive_table(conn),
    }


# =========================================================
# runner
# =========================================================


def make_context(*, bas_dd: date, dry_run: bool, verbose: bool) -> Context:
    ensure_env(require_db=True, require_krx=True, require_dart=True)
    return Context(
        bas_dd=bas_dd,
        dry_run=dry_run,
        verbose=verbose,
        krx=KRXClient(KRX_AUTH_KEY or "", KRX_API_BASE),
        dart=DARTClient(DART_API_KEY or "", DART_API_BASE),
        ipo_window_days=DEFAULT_IPO_WINDOW_DAYS,
    )


def run_job(
    job: str,
    *,
    bas_dd: date,
    dry_run: bool,
    verbose: bool,
    limit: Optional[int],
    price_days: int,
    disclosure_days: int,
    new_listing_lookback_days: int,
) -> dict[str, Any]:
    ctx = make_context(bas_dd=bas_dd, dry_run=dry_run, verbose=verbose)
    stats: dict[str, Any] = {"job": job, "bas_dd": iso(bas_dd), "dry_run": dry_run}

    with get_conn(autocommit=False) as conn:
        verify_required_tables(conn)
        sync_run_id: Optional[int] = None
        if not dry_run:
            sync_run_id = start_sync_run(conn, job_name=job, run_date=bas_dd)

        try:
            if job == "seed":
                stats["seed_recent_universe"] = seed_recent_universe(conn, ctx, limit=limit)
            elif job == "prices":
                stats["prices"] = sync_prices(conn, ctx, price_days=price_days, limit=limit)
            elif job == "disclosures":
                stats["disclosures"] = sync_disclosures(conn, ctx, disclosure_days=disclosure_days, limit=limit)
            elif job == "shareholders":
                stats["shareholders"] = sync_shareholders(conn, ctx, limit=limit)
            elif job == "purge":
                stats["purge"] = purge_expired(conn, ctx)
            elif job == "daily":
                stats["new_listings"] = add_new_listings(conn, ctx, lookback_days=new_listing_lookback_days)
                stats["prices"] = sync_prices(conn, ctx, price_days=price_days, limit=limit)
                stats["disclosures"] = sync_disclosures(conn, ctx, disclosure_days=disclosure_days, limit=limit)
                stats["shareholders"] = sync_shareholders(conn, ctx, limit=limit)
                stats["purge"] = purge_expired(conn, ctx)
            else:
                raise CollectorError(f"알 수 없는 job: {job}")

            if dry_run:
                conn.rollback()
            else:
                finish_sync_run(conn, sync_run_id=sync_run_id or 0, status="SUCCESS", stats=stats)
                conn.commit()
            return stats
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            if not dry_run and sync_run_id is not None:
                with get_conn(autocommit=True) as log_conn:
                    finish_sync_run(log_conn, sync_run_id=sync_run_id, status="FAILED", stats=stats, error_message=str(exc))
            raise


# =========================================================
# cli
# =========================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IPO Trace collector")
    parser.add_argument("job", choices=["seed", "daily", "prices", "disclosures", "shareholders", "purge"])
    parser.add_argument("--as-of", dest="as_of", help="기준일 YYYY-MM-DD 또는 YYYYMMDD")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--price-days", type=int, default=1)
    parser.add_argument("--disclosure-days", type=int, default=7)
    parser.add_argument("--new-listing-lookback-days", type=int, default=7)
    return parser.parse_args()


def parse_cli_date(raw: Optional[str]) -> date:
    if not raw:
        return previous_business_day()
    parsed = parse_krx_date(raw)
    if not parsed:
        raise CollectorError(f"날짜 형식이 잘못되었습니다: {raw}")
    return parsed


def main() -> None:
    args = parse_args()
    bas_dd = parse_cli_date(args.as_of)
    stats = run_job(
        args.job,
        bas_dd=bas_dd,
        dry_run=args.dry_run,
        verbose=args.verbose,
        limit=args.limit,
        price_days=args.price_days,
        disclosure_days=args.disclosure_days,
        new_listing_lookback_days=args.new_listing_lookback_days,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2, default=json_default))


if __name__ == "__main__":
    main()
