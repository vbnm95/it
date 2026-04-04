from __future__ import annotations

import re
import warnings
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO, StringIO
from typing import Any, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from settings import DART_API_BASE, DART_API_KEY, REQUEST_RETRIES, REQUEST_TIMEOUT
from utils import (
    DARTAPIError,
    log,
    normalize_holder_key,
    normalize_stock_code,
    normalize_text,
    parse_date,
    sleep_retry,
    to_decimal,
    to_int,
)


warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


@dataclass(frozen=True)
class DartDisclosureRow:
    rcept_no: str
    rcept_dt: date
    report_nm: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class DartLatestHolderRow:
    holder_key: str
    holder_name: str
    holder_role: Optional[str]
    latest_pct: Decimal
    latest_shares: Optional[int]
    source_rcept_no: Optional[str]
    source_date: Optional[date]
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class DartIpoHolderRow:
    holder_key: str
    holder_name: str
    holder_role: Optional[str]
    base_pct: Decimal
    base_shares: Optional[int]
    source_rcept_no: Optional[str]
    source_date: Optional[date]
    raw_payload: dict[str, Any]


class DARTClient:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.session = requests.Session()

    def _get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{DART_API_BASE.rstrip('/')}/{endpoint}"
        last_error: Exception | None = None

        for attempt in range(1, REQUEST_RETRIES + 1):
            try:
                resp = self.session.get(
                    url,
                    params={"crtfc_key": DART_API_KEY, **params},
                    timeout=REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                payload = resp.json()
                status = payload.get("status")
                if status in (None, "000", "013"):
                    return payload
                raise DARTAPIError(
                    f"{endpoint} status={status} message={payload.get('message')}"
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < REQUEST_RETRIES:
                    sleep_retry(attempt)

        raise DARTAPIError(f"DART 요청 실패: {endpoint} / {last_error}")

    def _download_document_zip(self, rcept_no: str) -> bytes:
        url = f"{DART_API_BASE.rstrip('/')}/document.xml"
        last_error: Exception | None = None

        for attempt in range(1, REQUEST_RETRIES + 1):
            try:
                resp = self.session.get(
                    url,
                    params={"crtfc_key": DART_API_KEY, "rcept_no": rcept_no},
                    timeout=60,
                )
                resp.raise_for_status()
                content = resp.content

                if not content.startswith(b"PK"):
                    preview = content[:500].decode("utf-8", errors="ignore")
                    if "<status>014</status>" in preview:
                        raise DARTAPIError(f"document.xml 문서 없음 / rcept_no={rcept_no}")
                    raise DARTAPIError(
                        f"document.xml 응답이 ZIP이 아님 / rcept_no={rcept_no} / preview={preview}"
                    )

                return content

            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < REQUEST_RETRIES:
                    sleep_retry(attempt)

        raise DARTAPIError(f"document.xml 다운로드 실패 / rcept_no={rcept_no} / {last_error}")

    def fetch_corp_code_map(self) -> dict[str, str]:
        url = f"{DART_API_BASE.rstrip('/')}/corpCode.xml"
        last_error: Exception | None = None

        for attempt in range(1, REQUEST_RETRIES + 1):
            try:
                resp = self.session.get(
                    url,
                    params={"crtfc_key": DART_API_KEY},
                    timeout=60,
                )
                resp.raise_for_status()
                archive = zipfile.ZipFile(BytesIO(resp.content))
                xml_name = archive.namelist()[0]
                root = ET.fromstring(archive.read(xml_name))

                out: dict[str, str] = {}
                for item in root.findall(".//list"):
                    corp_code = normalize_text(item.findtext("corp_code"))
                    stock_code = normalize_stock_code(item.findtext("stock_code"))
                    if corp_code and stock_code:
                        out[stock_code] = corp_code

                log(f"[DART] corp_code_map={len(out)}", verbose=self.verbose)
                return out
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < REQUEST_RETRIES:
                    sleep_retry(attempt)

        raise DARTAPIError(f"corpCode.xml 실패 / {last_error}")

    def fetch_disclosures(
        self,
        corp_code: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[DartDisclosureRow]:
        page_no = 1
        out: list[DartDisclosureRow] = []

        while True:
            payload = self._get_json(
                "list.json",
                {
                    "corp_code": corp_code,
                    "bgn_de": start_date.strftime("%Y%m%d"),
                    "end_de": end_date.strftime("%Y%m%d"),
                    "last_reprt_at": "Y",
                    "sort": "date",
                    "sort_mth": "desc",
                    "page_no": str(page_no),
                    "page_count": "100",
                },
            )

            rows = payload.get("list") or []
            for row in rows:
                if not isinstance(row, dict):
                    continue

                rcept_no = normalize_text(row.get("rcept_no"))
                rcept_dt = parse_date(row.get("rcept_dt"))
                report_nm = normalize_text(row.get("report_nm"))

                if rcept_no and rcept_dt and report_nm:
                    out.append(
                        DartDisclosureRow(
                            rcept_no=rcept_no,
                            rcept_dt=rcept_dt,
                            report_nm=report_nm,
                            raw_payload=row,
                        )
                    )

            total_page = int(payload.get("total_page") or 1)
            if page_no >= total_page:
                break
            page_no += 1

        return out

    def fetch_offering_info(self, corp_code: str, *, listing_date: date) -> dict[str, Any]:
        payload = self._get_json(
            "estkRs.json",
            {
                "corp_code": corp_code,
                "bgn_de": (listing_date - timedelta(days=365)).strftime("%Y%m%d"),
                "end_de": (listing_date + timedelta(days=60)).strftime("%Y%m%d"),
            },
        )

        group_rows: list[dict[str, Any]] = []
        for group in payload.get("group") or []:
            if not isinstance(group, dict):
                continue
            for row in group.get("list") or []:
                if isinstance(row, dict):
                    group_rows.append(row)

        if not group_rows:
            return {}

        group_rows.sort(key=lambda x: normalize_text(x.get("rcept_no")), reverse=True)
        target = group_rows[0]

        return {
            "offering_price": to_decimal(target.get("slprc")),
            "source_rcept_no": normalize_text(target.get("rcept_no")) or None,
        }

    def fetch_latest_holders(self, corp_code: str) -> list[DartLatestHolderRow]:
        payload = self._get_json("majorstock.json", {"corp_code": corp_code})
        rows = payload.get("list") or []
        dedup: dict[str, DartLatestHolderRow] = {}

        for row in rows:
            if not isinstance(row, dict):
                continue

            holder_name = normalize_text(row.get("repror"))
            if not holder_name:
                continue

            holder_key = normalize_holder_key(holder_name)
            if not holder_key:
                continue

            latest_pct = to_decimal(row.get("stkrt")) or Decimal("0")
            latest_shares = to_int(row.get("stkqy"))
            source_rcept_no = normalize_text(row.get("rcept_no")) or None
            source_date = parse_date(row.get("rcept_dt"))

            current = DartLatestHolderRow(
                holder_key=holder_key,
                holder_name=holder_name,
                holder_role=normalize_text(row.get("report_tp")) or None,
                latest_pct=latest_pct,
                latest_shares=latest_shares,
                source_rcept_no=source_rcept_no,
                source_date=source_date,
                raw_payload=row,
            )

            prev = dedup.get(holder_key)
            if prev is None:
                dedup[holder_key] = current
            else:
                prev_date = prev.source_date or date.min
                cur_date = current.source_date or date.min
                if cur_date > prev_date:
                    dedup[holder_key] = current

        out = list(dedup.values())
        out.sort(key=lambda x: (x.holder_name, x.holder_key))
        return out

    def fetch_ipo_holders(self, corp_code: str, *, listing_date: date) -> list[DartIpoHolderRow]:
        candidates = self._find_ipo_filing_candidates(
            corp_code=corp_code,
            listing_date=listing_date,
        )
        if not candidates:
            log(
                f"[DART][IPO_HOLDERS] no candidates corp_code={corp_code} listing_date={listing_date.isoformat()}",
                verbose=self.verbose,
            )
            return []

        for cand in candidates:
            try:
                rows = self._parse_ipo_holders_from_rcept_no(
                    rcept_no=cand["rcept_no"],
                    source_date=cand["rcept_dt"],
                )
                if rows:
                    log(
                        f"[DART][IPO_HOLDERS] matched rcept_no={cand['rcept_no']} rows={len(rows)} report_nm={cand['report_nm']}",
                        verbose=self.verbose,
                    )
                    return rows

                log(
                    f"[DART][IPO_HOLDERS] parsed but no holder rows rcept_no={cand['rcept_no']} report_nm={cand['report_nm']}",
                    verbose=self.verbose,
                )
            except Exception as exc:  # noqa: BLE001
                log(
                    f"[DART][IPO_HOLDERS] parse failed rcept_no={cand['rcept_no']} report_nm={cand['report_nm']} err={exc}",
                    verbose=self.verbose,
                )
                continue

        return []

    def _find_ipo_filing_candidates(self, *, corp_code: str, listing_date: date) -> list[dict[str, Any]]:
        start_date = listing_date - timedelta(days=540)
        end_date = listing_date + timedelta(days=7)
        rows = self.fetch_disclosures(corp_code, start_date=start_date, end_date=end_date)

        candidates: list[dict[str, Any]] = []

        for row in rows:
            name = normalize_text(row.report_nm)
            if "증권발행실적보고서" not in name:
                continue

            score = 100
            if "정정" in name:
                score -= 20

            day_gap = abs((listing_date - row.rcept_dt).days)
            score -= min(day_gap, 60)

            candidates.append(
                {
                    "rcept_no": row.rcept_no,
                    "rcept_dt": row.rcept_dt,
                    "report_nm": row.report_nm,
                    "score": score,
                }
            )

        candidates.sort(
            key=lambda x: (x["score"], x["rcept_dt"], x["rcept_no"]),
            reverse=True,
        )

        log(
            f"[DART][IPO_HOLDERS] candidate_count={len(candidates)} listing_date={listing_date.isoformat()} "
            f"candidates={[{'rcept_no': c['rcept_no'], 'rcept_dt': c['rcept_dt'].isoformat(), 'report_nm': c['report_nm']} for c in candidates[:5]]}",
            verbose=self.verbose,
        )

        return candidates

    def _parse_ipo_holders_from_rcept_no(self, *, rcept_no: str, source_date: date) -> list[DartIpoHolderRow]:
        raw_zip = self._download_document_zip(rcept_no)
        archive = zipfile.ZipFile(BytesIO(raw_zip))

        for name in archive.namelist():
            lower = name.lower()
            if not lower.endswith((".xml", ".xbrl", ".htm", ".html")):
                continue

            data = archive.read(name)
            rows = self._extract_ipo_holders_from_html_bytes(
                data=data,
                rcept_no=rcept_no,
                source_date=source_date,
            )
            if rows:
                return rows

        return []

    def _extract_ipo_holders_from_html_bytes(
        self,
        *,
        data: bytes,
        rcept_no: str,
        source_date: date,
    ) -> list[DartIpoHolderRow]:
        html = None
        for enc in ("utf-8", "cp949", "euc-kr"):
            try:
                html = data.decode(enc)
                break
            except Exception:
                continue

        if html is None:
            return []

        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        if not tables:
            return []

        best_rows: list[DartIpoHolderRow] = []
        best_score = -1

        for table_idx, table in enumerate(tables, start=1):
            table_html = str(table)

            try:
                dfs = pd.read_html(StringIO(table_html), header=[0, 1])
            except ValueError:
                try:
                    dfs = pd.read_html(StringIO(table_html), header=0)
                except Exception as exc:  # noqa: BLE001
                    log(
                        f"[DART][IPO_HOLDERS] read_html failed rcept_no={rcept_no} table_idx={table_idx} err={exc}",
                        verbose=self.verbose,
                    )
                    continue
            except Exception as exc:  # noqa: BLE001
                log(
                    f"[DART][IPO_HOLDERS] read_html failed rcept_no={rcept_no} table_idx={table_idx} err={exc}",
                    verbose=self.verbose,
                )
                continue

            for df_idx, df in enumerate(dfs, start=1):
                rows, score, debug_cols = self._dataframe_to_ipo_holders(
                    df=df,
                    rcept_no=rcept_no,
                    source_date=source_date,
                )

                log(
                    f"[DART][IPO_HOLDERS] table_idx={table_idx} df_idx={df_idx} score={score} rows={len(rows)} cols={debug_cols}",
                    verbose=self.verbose,
                )

                if rows and score > best_score:
                    best_rows = rows
                    best_score = score

        return best_rows

    def _dataframe_to_ipo_holders(
        self,
        *,
        df: pd.DataFrame,
        rcept_no: str,
        source_date: date,
    ) -> tuple[list[DartIpoHolderRow], int, list[str]]:
        work = df.copy()
        work.columns = self._flatten_columns(work.columns)
        debug_cols = [str(c) for c in work.columns]

        work = work.dropna(axis=1, how="all")
        work.columns = [normalize_text(str(c)) for c in work.columns]

        name_col = self._find_name_col(list(work.columns))
        stock_type_col = self._find_stock_type_col(list(work.columns))
        post_shares_col = self._find_post_shares_col(list(work.columns))
        post_pct_col = self._find_post_pct_col(list(work.columns))

        score = 0
        if name_col:
            score += 30
        if stock_type_col:
            score += 20
        if post_shares_col:
            score += 25
        if post_pct_col:
            score += 25

        if not name_col or not post_shares_col or not post_pct_col:
            return [], score, debug_cols

        parsed_rows: list[DartIpoHolderRow] = []

        for _, row in work.iterrows():
            holder_name = normalize_text(row.get(name_col))
            if not holder_name:
                continue

            compact_name = holder_name.replace(" ", "")
            if compact_name in ("소계", "합계", "계", "-"):
                continue
            if "소계" in compact_name or "합계" in compact_name:
                continue
            if compact_name in ("최대주주등", "5%이상소유주주", "5%이상소유주주등"):
                continue

            stock_type = normalize_text(row.get(stock_type_col)) if stock_type_col else ""
            base_shares = to_int(row.get(post_shares_col))
            base_pct = self._extract_pct_strict(row.get(post_pct_col))

            if base_pct is None:
                continue
            if base_pct < Decimal("0") or base_pct > Decimal("100"):
                continue

            holder_key = normalize_holder_key(holder_name)
            if not holder_key:
                continue

            parsed_rows.append(
                DartIpoHolderRow(
                    holder_key=holder_key,
                    holder_name=holder_name,
                    holder_role=None,
                    base_pct=base_pct,
                    base_shares=base_shares,
                    source_rcept_no=rcept_no,
                    source_date=source_date,
                    raw_payload={
                        "stock_type": stock_type or None,
                        "columns": list(work.columns),
                        "row": {k: self._safe_str(v) for k, v in row.to_dict().items()},
                    },
                )
            )

        parsed_rows = self._dedup_holder_rows(parsed_rows)
        score += len(parsed_rows)

        return parsed_rows, score, debug_cols

    def _flatten_columns(self, columns: Any) -> list[str]:
        flattened: list[str] = []

        if isinstance(columns, pd.MultiIndex):
            for col in columns:
                parts = [normalize_text(str(x)) for x in col]
                parts = [p for p in parts if p and "Unnamed" not in p and p != "nan"]

                merged = " ".join(parts)
                merged = re.sub(r"\s+", " ", merged).strip()
                flattened.append(self._normalize_column_name(merged))
            return flattened

        for col in columns:
            text = normalize_text(str(col))
            text = re.sub(r"\s+", " ", text).strip()
            flattened.append(self._normalize_column_name(text))
        return flattened

    def _normalize_column_name(self, col: str) -> str:
        text = normalize_text(col)
        text = text.replace("\n", " ")
        text = re.sub(r"\s+", " ", text).strip()
        no_space = text.replace(" ", "")

        if "성명" in no_space or "주주명" in no_space:
            return "성명"

        if "주식의종류" in no_space or "주식종류" in no_space:
            return "주식의 종류"

        if ("공모후" in no_space or "증자후" in no_space) and "주식수" in no_space:
            return "공모후 주식수"

        if ("공모후" in no_space or "증자후" in no_space) and "지분율" in no_space:
            return "공모후 지분율"

        if ("공모전" in no_space or "증자전" in no_space) and "주식수" in no_space:
            return "공모전 주식수"

        if ("공모전" in no_space or "증자전" in no_space) and "지분율" in no_space:
            return "공모전 지분율"

        return text

    def _find_name_col(self, columns: list[str]) -> Optional[str]:
        for col in columns:
            normalized = normalize_text(col).replace(" ", "")
            if normalized == "성명":
                return col
        for col in columns:
            normalized = normalize_text(col).replace(" ", "")
            if "성명" in normalized or "주주명" in normalized:
                return col
        return None

    def _find_stock_type_col(self, columns: list[str]) -> Optional[str]:
        for col in columns:
            normalized = normalize_text(col).replace(" ", "")
            if normalized == "주식의종류" or normalized == "주식종류":
                return col
        for col in columns:
            normalized = normalize_text(col).replace(" ", "")
            if "주식" in normalized and "종류" in normalized:
                return col
        return None

    def _find_post_shares_col(self, columns: list[str]) -> Optional[str]:
        for col in columns:
            normalized = normalize_text(col).replace(" ", "")
            if ("공모후" in normalized or "증자후" in normalized) and "주식수" in normalized:
                return col

        for col in columns:
            normalized = normalize_text(col).replace(" ", "")
            if normalized == "주식수":
                return col

        return None

    def _find_post_pct_col(self, columns: list[str]) -> Optional[str]:
        for col in columns:
            normalized = normalize_text(col).replace(" ", "")
            if ("공모후" in normalized or "증자후" in normalized) and "지분율" in normalized:
                return col

        for col in columns:
            normalized = normalize_text(col).replace(" ", "")
            if normalized == "지분율":
                return col

        return None

    def _extract_pct_strict(self, value: Any) -> Optional[Decimal]:
        text = normalize_text(value)
        if not text:
            return None

        text = text.replace("%", "")
        text = re.sub(r"[^0-9\.\-]", "", text)
        if not text:
            return None

        try:
            pct = Decimal(text).quantize(Decimal("0.0001"))
        except Exception:
            return None

        if pct < 0 or pct > 100:
            return None

        return pct

    def _dedup_holder_rows(self, rows: list[DartIpoHolderRow]) -> list[DartIpoHolderRow]:
        dedup: dict[str, DartIpoHolderRow] = {}

        for row in rows:
            prev = dedup.get(row.holder_key)
            if prev is None:
                dedup[row.holder_key] = row
            else:
                if row.base_pct > prev.base_pct:
                    dedup[row.holder_key] = row

        out = list(dedup.values())
        out.sort(key=lambda x: (x.holder_name, x.holder_key))
        return out

    def _safe_str(self, value: Any) -> str:
        if value is None:
            return ""
        try:
            return str(value)
        except Exception:
            return ""