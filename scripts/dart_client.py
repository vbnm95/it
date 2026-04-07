from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from html import unescape
from typing import Any, Optional
from xml.etree import ElementTree as ET

import requests

from settings import DART_API_BASE, DART_API_KEY, REQUEST_RETRIES, REQUEST_TIMEOUT
from utils import (
    DARTAPIError,
    log,
    normalize_holder_key,
    normalize_stock_code,
    normalize_text,
    parse_date,
    quant2,
    quant4,
    sleep_retry,
    to_decimal,
    to_int,
)


@dataclass(frozen=True)
class DartFiling:
    rcept_no: str
    report_nm: str
    rcept_dt: date


class DARTClient:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.session = requests.Session()
        self._corp_code_by_stock_code: dict[str, str] | None = None
        self._corp_name_by_stock_code: dict[str, str] | None = None

    # =========================================================
    # public
    # =========================================================
    def resolve_corp_code(self, stock_code: str) -> Optional[str]:
        self._ensure_corp_codes()
        assert self._corp_code_by_stock_code is not None
        return self._corp_code_by_stock_code.get(stock_code)

    def fetch_ipo_snapshot(
        self,
        *,
        stock_code: str,
        company_name: str,
        listing_date: date,
    ) -> dict[str, Any]:
        corp_code = self.resolve_corp_code(stock_code)
        if not corp_code:
            return {
                "corp_code": None,
                "offering_price": None,
                "offering_price_source": None,
                "offering_price_source_rcept_no": None,
                "ipo_holders": [],
                "ipo_filing": None,
            }

        candidates = self._find_ipo_filing_candidates(corp_code=corp_code, listing_date=listing_date)
        if not candidates:
            return {
                "corp_code": corp_code,
                "offering_price": None,
                "offering_price_source": None,
                "offering_price_source_rcept_no": None,
                "ipo_holders": [],
                "ipo_filing": None,
            }

        best = candidates[0]
        xml_text = self._download_document_xml(best.rcept_no)
        offering_price = self._extract_offering_price(xml_text=xml_text)
        ipo_holders = self._extract_ipo_holders(
            xml_text=xml_text,
            rcept_no=best.rcept_no,
            source_date=best.rcept_dt,
        )

        return {
            "corp_code": corp_code,
            "offering_price": offering_price,
            "offering_price_source": "DART_SECURITIES_ISSUANCE_RESULT" if offering_price is not None else None,
            "offering_price_source_rcept_no": best.rcept_no if offering_price is not None else None,
            "ipo_holders": ipo_holders,
            "ipo_filing": best,
        }

    def fetch_recent_disclosures(
        self,
        *,
        corp_code: str,
        end_date: date,
        days_back: int,
        limit: int = 20,
    ) -> list[DartFiling]:
        begin_date = end_date - timedelta(days=max(days_back, 1) - 1)
        rows = self._list_filings(
            corp_code=corp_code,
            begin_date=begin_date,
            end_date=end_date,
            page_count=max(limit, 20),
        )
        rows = sorted(rows, key=lambda x: (x.rcept_dt, x.rcept_no), reverse=True)
        return rows[:limit]

    def fetch_latest_major_shareholders(
        self,
        *,
        corp_code: str,
        listing_date: date,
    ) -> list[dict[str, Any]]:
        candidates = self._find_major_shareholder_candidates(corp_code=corp_code, listing_date=listing_date)
        for filing in candidates:
            try:
                xml_text = self._download_document_xml(filing.rcept_no)
                rows = self._extract_latest_major_shareholders(
                    xml_text=xml_text,
                    rcept_no=filing.rcept_no,
                    source_date=filing.rcept_dt,
                )
                if rows:
                    return rows
            except Exception as exc:  # noqa: BLE001
                log(
                    f"[DART][WARN] latest major shareholder parse failed: {filing.rcept_no} / {exc}",
                    verbose=self.verbose,
                )
        return []
    
    def _is_pure_public_ipo_filing(self, report_nm: str) -> bool:
        name = normalize_text(report_nm).replace(" ", "")
        if not name:
            return False

        if "증권발행실적보고서" not in name:
            return False

        excluded_keywords = (
            "합병",
            "합병등",
            "분할",
            "분할합병",
            "주식교환",
            "주식이전",
            "재상장",
            "우회상장",
            "집합투자증권",
            "수익증권",
            "투자회사",
            "리츠",
            "REIT",
        )

        if any(keyword in name for keyword in excluded_keywords):
            return False

        return True

    # =========================================================
    # DART API helpers
    # =========================================================
    def _ensure_corp_codes(self) -> None:
        if self._corp_code_by_stock_code is not None:
            return

        if not DART_API_KEY:
            raise DARTAPIError("DART_API_KEY 환경변수가 필요합니다.")

        url = f"{DART_API_BASE.rstrip('/')}/corpCode.xml"
        last_error: Exception | None = None

        for attempt in range(1, REQUEST_RETRIES + 1):
            try:
                resp = self.session.get(
                    url,
                    params={"crtfc_key": DART_API_KEY},
                    timeout=REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                root = self._open_zip_xml(resp.content)

                corp_code_by_stock_code: dict[str, str] = {}
                corp_name_by_stock_code: dict[str, str] = {}

                for elem in root.findall(".//list"):
                    stock_code = normalize_stock_code(elem.findtext("stock_code"))
                    corp_code = normalize_text(elem.findtext("corp_code"))
                    corp_name = normalize_text(elem.findtext("corp_name"))

                    if stock_code and corp_code:
                        corp_code_by_stock_code[stock_code] = corp_code
                        corp_name_by_stock_code[stock_code] = corp_name

                self._corp_code_by_stock_code = corp_code_by_stock_code
                self._corp_name_by_stock_code = corp_name_by_stock_code
                log(f"[DART] corp codes loaded={len(corp_code_by_stock_code)}", verbose=self.verbose)
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < REQUEST_RETRIES:
                    sleep_retry(attempt)

        raise DARTAPIError(f"DART corpCode 조회 실패 / {last_error}")

    def _call_json(self, endpoint: str, *, params: dict[str, Any]) -> dict[str, Any]:
        if not DART_API_KEY:
            raise DARTAPIError("DART_API_KEY 환경변수가 필요합니다.")

        url = f"{DART_API_BASE.rstrip('/')}/{endpoint.lstrip('/')}"
        query = {"crtfc_key": DART_API_KEY, **params}
        last_error: Exception | None = None

        for attempt in range(1, REQUEST_RETRIES + 1):
            try:
                resp = self.session.get(url, params=query, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                payload = resp.json()

                status = str(payload.get("status", ""))
                if status and status != "000":
                    message = payload.get("message") or "DART API 오류"
                    if status == "013":
                        return {"list": []}
                    raise DARTAPIError(f"{endpoint} / status={status} / {message}")

                return payload
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < REQUEST_RETRIES:
                    sleep_retry(attempt)

        raise DARTAPIError(f"DART 요청 실패: {endpoint} / {last_error}")

    def _list_filings(
        self,
        *,
        corp_code: str,
        begin_date: date,
        end_date: date,
        page_count: int = 100,
    ) -> list[DartFiling]:
        payload = self._call_json(
            "list.json",
            params={
                "corp_code": corp_code,
                "bgn_de": begin_date.strftime("%Y%m%d"),
                "end_de": end_date.strftime("%Y%m%d"),
                "page_no": 1,
                "page_count": page_count,
                "last_reprt_at": "N",
            },
        )

        out: list[DartFiling] = []
        for row in payload.get("list") or []:
            rcept_no = normalize_text(row.get("rcept_no"))
            report_nm = normalize_text(row.get("report_nm"))
            rcept_dt = parse_date(row.get("rcept_dt"))
            if rcept_no and report_nm and rcept_dt:
                out.append(DartFiling(rcept_no=rcept_no, report_nm=report_nm, rcept_dt=rcept_dt))

        return out

    def _download_document_xml(self, rcept_no: str) -> str:
        if not DART_API_KEY:
            raise DARTAPIError("DART_API_KEY 환경변수가 필요합니다.")

        url = f"{DART_API_BASE.rstrip('/')}/document.xml"
        last_error: Exception | None = None

        for attempt in range(1, REQUEST_RETRIES + 1):
            try:
                resp = self.session.get(
                    url,
                    params={"crtfc_key": DART_API_KEY, "rcept_no": rcept_no},
                    timeout=REQUEST_TIMEOUT,
                )
                resp.raise_for_status()

                content = resp.content
                content_type = resp.headers.get("Content-Type", "")

                if self._looks_like_zip(content):
                    return self._open_zip_xml_as_text(content)

                decoded = self._safe_decode(content)
                dart_error = self._extract_dart_error_message(decoded)
                if dart_error:
                    raise DARTAPIError(f"DART document 응답 오류: {rcept_no} / {dart_error}")

                preview = decoded[:500].strip()
                raise DARTAPIError(
                    f"DART document 응답이 zip이 아님: {rcept_no} / "
                    f"content-type={content_type or '-'} / preview={preview}"
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < REQUEST_RETRIES:
                    sleep_retry(attempt)

        raise DARTAPIError(f"DART document 다운로드 실패: {rcept_no} / {last_error}")
    
    def _find_ipo_filing_candidates(self, *, corp_code: str, listing_date: date) -> list[DartFiling]:
        rows = self._list_filings(
            corp_code=corp_code,
            begin_date=listing_date - timedelta(days=180),
            end_date=listing_date + timedelta(days=30),
            page_count=100,
        )

        candidates = [row for row in rows if self._is_pure_public_ipo_filing(row.report_nm)]
        candidates.sort(
            key=lambda x: (
                abs((x.rcept_dt - listing_date).days),
                -int(x.rcept_dt.strftime("%Y%m%d")),
                -int(x.rcept_no),
            )
        )
        return candidates

    def _find_major_shareholder_candidates(self, *, corp_code: str, listing_date: date) -> list[DartFiling]:
        rows = self._list_filings(
            corp_code=corp_code,
            begin_date=listing_date,
            end_date=date.today(),
            page_count=100,
        )

        keywords = (
            "주식등의대량보유상황보고서",
            "최대주주등소유주식변동신고서",
            "임원ㆍ주요주주특정증권등소유상황보고서",
            "임원ㆍ주요주주 소유보고",
            "소유주식변동",
        )

        candidates = [row for row in rows if any(keyword in row.report_nm for keyword in keywords)]
        candidates.sort(key=lambda x: (x.rcept_dt, x.rcept_no), reverse=True)
        return candidates

    # =========================================================
    # XML / text helpers
    # =========================================================
    def _looks_like_zip(self, content: bytes) -> bool:
        return len(content) >= 4 and content[:4] == b"PK\x03\x04"

    def _safe_decode(self, content: bytes) -> str:
        for encoding in ("utf-8", "euc-kr", "cp949"):
            try:
                return content.decode(encoding, errors="replace")
            except Exception:
                pass
        return content.decode("utf-8", errors="replace")

    def _clean_xml_text(self, text: str) -> str:
        return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)

    def _extract_dart_error_message(self, text: str) -> Optional[str]:
        status_match = re.search(r"<status>\s*([0-9]+)\s*</status>", text, flags=re.IGNORECASE)
        message_match = re.search(r"<message>\s*(.*?)\s*</message>", text, flags=re.IGNORECASE | re.DOTALL)
        if status_match or message_match:
            status = status_match.group(1) if status_match else "-"
            message = message_match.group(1).strip() if message_match else "알 수 없는 오류"
            return f"status={status}, message={message}"
        return None

    def _open_zip_xml(self, payload: bytes) -> ET.Element:
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            xml_names = [name for name in zf.namelist() if name.lower().endswith(".xml")]
            if not xml_names:
                raise DARTAPIError("ZIP 내부 XML 없음")
            with zf.open(xml_names[0]) as fp:
                return ET.parse(fp).getroot()

    def _open_zip_xml_as_text(self, payload: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            xml_names = [name for name in zf.namelist() if name.lower().endswith(".xml")]
            if not xml_names:
                raise DARTAPIError("ZIP 내부 XML 없음")
            with zf.open(xml_names[0]) as fp:
                raw = fp.read()
        return self._clean_xml_text(self._safe_decode(raw))

    # =========================================================
    # section extraction
    # =========================================================
    def _extract_section_block(
        self,
        *,
        xml_text: str,
        start_patterns: list[str],
        end_patterns: list[str],
    ) -> Optional[str]:
        lower_xml = xml_text.lower()
        start_pos: Optional[int] = None
        end_pos: Optional[int] = None

        for pattern in start_patterns:
            m = re.search(pattern, lower_xml, flags=re.IGNORECASE)
            if m:
                start_pos = m.start()
                break
        if start_pos is None:
            return None

        for pattern in end_patterns:
            m = re.search(pattern, lower_xml[start_pos + 1 :], flags=re.IGNORECASE)
            if m:
                end_pos = start_pos + 1 + m.start()
                break

        if end_pos is None:
            end_pos = len(xml_text)

        return xml_text[start_pos:end_pos]

    # =========================================================
    # html / table helpers
    # =========================================================
    def _strip_tags(self, html_text: str) -> str:
        text = re.sub(r"(?is)<br\s*/?>", " ", html_text)
        text = re.sub(r"(?is)</p>", " ", text)
        text = re.sub(r"(?is)</div>", " ", text)
        text = re.sub(r"(?is)<[^>]+>", " ", text)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _normalize_cell(self, value: str) -> str:
        text = normalize_text(value)
        text = text.replace("\xa0", " ")
        return text.strip()

    def _parse_span(self, attrs: str, attr_name: str) -> int:
        m = re.search(rf'{attr_name}\s*=\s*["\']?(\d+)["\']?', attrs, flags=re.IGNORECASE)
        if not m:
            return 1
        try:
            value = int(m.group(1))
            return value if value >= 1 else 1
        except ValueError:
            return 1

    def _parse_html_table(self, table_html: str) -> list[list[str]]:
        tr_matches = list(re.finditer(r"(?is)<tr[^>]*>(.*?)</tr>", table_html))
        if not tr_matches:
            return []

        grid: list[list[Optional[str]]] = []
        pending_rowspans: dict[tuple[int, int], str] = {}

        for r_idx, tr_match in enumerate(tr_matches):
            tr_html = tr_match.group(1)

            while len(grid) <= r_idx:
                grid.append([])

            row = grid[r_idx]
            c_idx = 0

            while (r_idx, c_idx) in pending_rowspans:
                row.append(pending_rowspans.pop((r_idx, c_idx)))
                c_idx += 1

            cell_matches = list(re.finditer(r"(?is)<t[dh]\b([^>]*)>(.*?)</t[dh]>", tr_html))
            for cell_match in cell_matches:
                attrs = cell_match.group(1) or ""
                inner_html = cell_match.group(2) or ""

                while (r_idx, c_idx) in pending_rowspans:
                    row.append(pending_rowspans.pop((r_idx, c_idx)))
                    c_idx += 1

                rowspan = self._parse_span(attrs, "rowspan")
                colspan = self._parse_span(attrs, "colspan")
                cell_text = self._normalize_cell(self._strip_tags(inner_html))

                for _ in range(colspan):
                    row.append(cell_text)
                    if rowspan > 1:
                        for rr in range(1, rowspan):
                            pending_rowspans[(r_idx + rr, c_idx)] = cell_text
                    c_idx += 1

            while (r_idx, c_idx) in pending_rowspans:
                row.append(pending_rowspans.pop((r_idx, c_idx)))
                c_idx += 1

        max_cols = max((len(r) for r in grid), default=0)
        out: list[list[str]] = []
        for row in grid:
            padded = row + [None] * (max_cols - len(row))
            normalized = [self._normalize_cell(x or "") for x in padded]
            if any(cell for cell in normalized):
                out.append(normalized)

        return out

    def _extract_tables_with_html(self, xml_text: str) -> list[list[list[str]]]:
        tables: list[list[list[str]]] = []
        for table_match in re.finditer(r"(?is)<table[^>]*>.*?</table>", xml_text):
            rows = self._parse_html_table(table_match.group(0))
            if rows:
                tables.append(rows)
        return tables

    def _to_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        text = self._normalize_cell(str(value))
        if not text:
            return None
        text = text.replace(",", "").replace("주", "").strip()
        if not text or text == "-":
            return None
        return to_int(text)

    def _to_decimal(self, value: Any) -> Optional[Decimal]:
        if value is None:
            return None
        text = self._normalize_cell(str(value))
        if not text:
            return None
        text = (
            text.replace(",", "")
            .replace("%", "")
            .replace("％", "")
            .replace("주", "")
            .strip()
        )
        if not text or text == "-":
            return None
        return to_decimal(text)

    def _make_holder_key(self, holder_name: Any) -> str:
        return normalize_holder_key(holder_name)

    # =========================================================
    # section III - scoring / selection
    # =========================================================
    def _score_ipo_table(self, rows: list[list[str]]) -> int:
        flat = " ".join(" ".join(row) for row in rows)
        flat_no_space = flat.replace(" ", "")
        score = 0

        if "주주" in flat:
            score += 5
        if "성명" in flat or "주주명" in flat:
            score += 6
        if "지분율" in flat or "%" in flat:
            score += 4
        if "주식수" in flat:
            score += 4
        if "공모전" in flat_no_space or "공모후" in flat_no_space:
            score += 6
        if "증자전" in flat_no_space or "증자후" in flat_no_space:
            score += 6
        if "최대주주" in flat or "주요주주" in flat:
            score += 2
        if len(rows) >= 4:
            score += 2

        if len(rows) == 1 and len(rows[0]) == 1 and "단위" in rows[0][0]:
            score -= 100

        return score

    def _find_section3_table(self, section_html: str) -> Optional[list[list[str]]]:
        tables = self._extract_tables_with_html(section_html)
        if not tables:
            return None

        scored = sorted(((self._score_ipo_table(table), table) for table in tables), key=lambda x: x[0], reverse=True)
        if not scored or scored[0][0] <= 0:
            return None
        return scored[0][1]

    # =========================================================
    # section III - header normalize / flatten
    # =========================================================
    def _normalize_header_token(self, value: str) -> str:
        text = normalize_text(value)
        text = text.replace(" ", "").replace("\n", "").replace("\xa0", "")
        text = text.replace("주주명(명칭)", "주주명")
        text = text.replace("성명", "주주명")
        text = text.replace("주식종류", "주식의종류")
        text = text.replace("공모전", "BEFORE")
        text = text.replace("증자전", "BEFORE")
        text = text.replace("공모후", "AFTER")
        text = text.replace("증자후", "AFTER")
        text = text.replace("소유주식수", "SHARES")
        text = text.replace("보유주식수", "SHARES")
        text = text.replace("주식수", "SHARES")
        text = text.replace("소유비율", "PCT")
        text = text.replace("지분율", "PCT")
        text = text.replace("%", "PCT")
        return text

    def _dedupe_repeated_text(self, value: str) -> str:
        text = self._normalize_cell(value)
        if not text:
            return ""

        for unit_len in range(1, max(1, len(text) // 2) + 1):
            if len(text) % unit_len != 0:
                continue
            unit = text[:unit_len]
            if unit and unit * (len(text) // unit_len) == text:
                return unit
        return text

    def _canonicalize_header_token(self, token: str) -> str:
        token = self._dedupe_repeated_text(token)
        token = self._normalize_cell(token)
        if not token:
            return ""

        compact = re.sub(r"\s+", "", token).upper()

        if compact in {"구분", "항목", "항목항목", "항목항목항목", "GROUP"}:
            return "GROUP"
        if compact in {"이름", "주주명", "성명", "HOLDERNAME", "NAME"}:
            return "HOLDER_NAME"
        if compact in {"관계", "RELATION"}:
            return "RELATION"
        if compact in {"주식의종류", "주식종류", "STOCKTYPE"}:
            return "STOCK_TYPE"
        if compact in {"비고", "NOTE"}:
            return "NOTE"
        if compact in {"상장전", "공모전", "BEFORE"}:
            return "BEFORE"
        if compact in {"상장후", "공모후", "AFTER"}:
            return "AFTER"
        if compact in {"주식수", "주식", "SHARES"}:
            return "SHARES"
        if compact in {"지분율", "PCT", "%"}:
            return "PCT"

        if compact in {"상장전주식", "공모전주식", "BEFORESHARES"}:
            return "BEFORE_SHARES"
        if compact in {"상장전지분율", "상장전PCT", "공모전PCT", "BEFOREPCT"}:
            return "BEFORE_PCT"
        if compact in {"상장후주식", "상장후SHARES", "공모후주식", "AFTERSHARES"}:
            return "AFTER_SHARES"
        if compact in {"상장후지분율", "상장후PCT", "공모후PCT", "AFTERPCT"}:
            return "AFTER_PCT"

        return compact

    def _is_header_like_row(self, row: list[str]) -> bool:
        normalized_cells = [self._normalize_header_token(x) for x in row if x]
        joined = " ".join(normalized_cells)
        if not joined:
            return False

        structural_tokens = ("구분", "주주명", "관계", "주식의종류", "BEFORE", "AFTER", "SHARES", "PCT")
        score = sum(1 for token in structural_tokens if token in joined)
        num_count = len(re.findall(r"\d[\d,]*", joined))
        if num_count >= 2:
            return False
        return score >= 2

    def _find_header_row_count(self, table: list[list[str]], max_header_rows: int = 3) -> int:
        header_count = 0
        scan_limit = min(len(table), max_header_rows + 2)

        for i in range(scan_limit):
            if self._is_header_like_row(table[i]):
                header_count += 1
            else:
                break

        return min(max(header_count, 1), max_header_rows)

    def _canonicalize_flattened_header(self, value: str) -> str:
        v = value

        if "구분" in v:
            return "GROUP"
        if "주주명" in v:
            return "HOLDER_NAME"
        if "주식의종류" in v:
            return "STOCK_TYPE"
        if "관계" in v:
            return "RELATION"
        if "BEFORE" in v and "SHARES" in v:
            return "BEFORE_SHARES"
        if "BEFORE" in v and "PCT" in v:
            return "BEFORE_PCT"
        if "AFTER" in v and "SHARES" in v:
            return "AFTER_SHARES"
        if "AFTER" in v and "PCT" in v:
            return "AFTER_PCT"

        return v

    def _canonicalize_flattened_headers(self, headers: list[str]) -> list[str]:
        canonical: list[str] = []

        for header in headers:
            parts = [self._canonicalize_header_token(x) for x in re.split(r"[|/>\-]+", str(header))]
            parts = [p for p in parts if p]

            joined = "_".join(parts)
            joined = joined.replace("GROUP_GROUP", "GROUP")
            joined = joined.replace("HOLDER_NAME_HOLDER_NAME", "HOLDER_NAME")
            joined = joined.replace("NOTE_NOTE", "NOTE")
            joined = joined.replace("BEFORE_SHARES_SHARES", "BEFORE_SHARES")
            joined = joined.replace("AFTER_SHARES_SHARES", "AFTER_SHARES")
            joined = joined.replace("BEFORE_PCT_PCT", "BEFORE_PCT")
            joined = joined.replace("AFTER_PCT_PCT", "AFTER_PCT")

            if joined in {"BEFORE_SHARES", "BEFORE_PCT", "AFTER_SHARES", "AFTER_PCT"}:
                canonical.append(joined)
                continue

            if parts == ["BEFORE", "SHARES"]:
                canonical.append("BEFORE_SHARES")
            elif parts == ["BEFORE", "PCT"]:
                canonical.append("BEFORE_PCT")
            elif parts == ["AFTER", "SHARES"]:
                canonical.append("AFTER_SHARES")
            elif parts == ["AFTER", "PCT"]:
                canonical.append("AFTER_PCT")
            elif parts:
                canonical.append(parts[-1])
            else:
                canonical.append("")

        fixed: list[str] = [self._dedupe_repeated_text(h) for h in canonical]

        repaired: list[str] = []
        before_seen = 0
        after_seen = 0

        for h in fixed:
            if h == "BEFORE_SHARES":
                before_seen += 1
                repaired.append("BEFORE_SHARES" if before_seen == 1 else "BEFORE_PCT")
            elif h == "AFTER_SHARES":
                after_seen += 1
                repaired.append("AFTER_SHARES" if after_seen == 1 else "AFTER_PCT")
            else:
                repaired.append(h)

        return repaired

    def _repair_single_row_before_after_headers(self, headers: list[str]) -> list[str]:
        if not headers:
            return headers

        if any(h in {"BEFORE_SHARES", "BEFORE_PCT", "AFTER_SHARES", "AFTER_PCT"} for h in headers):
            return headers

        repaired = headers[:]
        pending: Optional[str] = None

        for idx, header in enumerate(headers):
            if header == "BEFORE":
                repaired[idx] = "BEFORE_SHARES"
                pending = "BEFORE"
                continue

            if header == "AFTER":
                repaired[idx] = "AFTER_SHARES"
                pending = "AFTER"
                continue

            if header == "PCT" and pending == "BEFORE":
                repaired[idx] = "BEFORE_PCT"
                pending = None
                continue

            if header == "PCT" and pending == "AFTER":
                repaired[idx] = "AFTER_PCT"
                pending = None
                continue

            if header not in {"", "NOTE", "비고"}:
                pending = None

        return repaired

    def _flatten_headers(self, table: list[list[str]], header_row_count: int) -> list[str]:
        max_cols = max(len(r) for r in table)
        header_rows: list[list[str]] = []

        for i in range(header_row_count):
            row = table[i] if i < len(table) else []
            padded = row + [""] * (max_cols - len(row))
            header_rows.append([self._normalize_header_token(x) for x in padded])

        flattened: list[str] = []
        for c in range(max_cols):
            parts = [header_rows[r][c] for r in range(header_row_count) if header_rows[r][c]]
            merged = "".join(parts)
            flattened.append(self._canonicalize_flattened_header(merged))

        flattened = self._canonicalize_flattened_headers(flattened)

        if header_row_count == 1:
            flattened = self._repair_single_row_before_after_headers(flattened)

        return flattened

    def _looks_like_sum_row(self, holder_name: str) -> bool:
        text = holder_name.replace(" ", "")
        return text in {"소계", "합계", "계", "총계"}

    def _looks_like_non_holder_row(self, holder_name: str) -> bool:
        text = self._normalize_cell(holder_name)
        compact = re.sub(r"\s+", "", text)

        if not compact:
            return False

        if compact in {"발행주식총수", "총발행주식수", "발행주식수"}:
            return True

        if compact.startswith("주석"):
            return True

        if re.fullmatch(r"주\d+\)?", compact):
            return True

        return False

    def _to_pct_decimal(self, value: str) -> Optional[Decimal]:
        raw = self._normalize_cell(value)
        raw = raw.replace("%", "").replace("％", "").strip()
        return to_decimal(raw)

    # =========================================================
    # section III - parse
    # =========================================================
    def _parse_ipo_holder_table(
        self,
        *,
        table: list[list[str]],
        rcept_no: str,
        source_date: date,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        if len(table) < 2:
            return [], []

        header_row_count = self._find_header_row_count(table, max_header_rows=3)
        flattened_headers = self._flatten_headers(table, header_row_count=header_row_count)

        def find_idx(*targets: str) -> Optional[int]:
            normalized_targets = {self._canonicalize_header_token(t) for t in targets}
            for idx, header in enumerate(flattened_headers):
                header_norm = self._canonicalize_header_token(header)
                if header_norm in normalized_targets:
                    return idx
            return None

        name_idx = find_idx("HOLDER_NAME", "이름", "주주명", "성명")
        stock_type_idx = find_idx("STOCK_TYPE", "주식종류", "주식의종류")
        before_shares_idx = find_idx("BEFORE_SHARES", "상장전주식", "공모전주식")
        before_pct_idx = find_idx("BEFORE_PCT", "상장전PCT", "상장전지분율", "공모전지분율")
        after_shares_idx = find_idx("AFTER_SHARES", "상장후주식", "상장후SHARES", "공모후주식")
        after_pct_idx = find_idx("AFTER_PCT", "상장후PCT", "상장후지분율", "공모후지분율")

        if name_idx is None or after_shares_idx is None or after_pct_idx is None:
            log(f"[DART][WARN] IPO header parse failed / headers={flattened_headers}", verbose=self.verbose)
            return [], flattened_headers

        out: list[dict[str, Any]] = []
        max_cols = max(len(r) for r in table)

        for raw_row in table[header_row_count:]:
            row = [self._normalize_cell(x) for x in raw_row] + [""] * (max_cols - len(raw_row))

            if all(not x for x in row):
                continue

            holder_name = row[name_idx] if name_idx is not None and name_idx < len(row) else ""
            if not holder_name:
                continue
            if self._looks_like_sum_row(holder_name):
                continue
            if self._looks_like_non_holder_row(holder_name):
                continue
            if holder_name.replace(" ", "") in {"주주명", "성명", "이름"}:
                continue
            if re.fullmatch(r"[\d,\.%]+", holder_name):
                continue

            stock_type_value = row[stock_type_idx] if stock_type_idx is not None and stock_type_idx < len(row) else ""

            before_shares_raw = row[before_shares_idx] if before_shares_idx is not None and before_shares_idx < len(row) else ""
            before_pct_raw = row[before_pct_idx] if before_pct_idx is not None and before_pct_idx < len(row) else ""
            after_shares_raw = row[after_shares_idx] if after_shares_idx is not None and after_shares_idx < len(row) else ""
            after_pct_raw = row[after_pct_idx] if after_pct_idx is not None and after_pct_idx < len(row) else ""

            base_shares = self._to_int(before_shares_raw)
            base_pct = self._to_decimal(before_pct_raw)
            after_shares = self._to_int(after_shares_raw)
            after_pct = self._to_decimal(after_pct_raw)

            if after_pct is not None and after_pct > Decimal("1000") and after_shares is None:
                maybe_shares = self._to_int(after_pct_raw)
                maybe_pct = self._to_pct_decimal(after_shares_raw)
                if maybe_pct is not None and maybe_pct <= Decimal("100"):
                    after_shares = maybe_shares
                    after_pct = maybe_pct

            final_base_shares = after_shares if after_shares is not None else base_shares
            final_base_pct = after_pct if after_pct is not None else base_pct

            if final_base_shares is None and final_base_pct is None:
                continue

            holder_key = self._make_holder_key(holder_name)
            if not holder_key:
                continue

            holder_role = stock_type_value or None

            out.append(
                {
                    "holder_key": holder_key,
                    "holder_name": holder_name,
                    "holder_role": holder_role,
                    "base_pct": quant4(final_base_pct) if final_base_pct is not None else Decimal("0"),
                    "base_shares": final_base_shares,
                    "source_rcept_no": rcept_no,
                    "source_date": source_date,
                }
            )

        return (
            self._merge_holder_rows(
                rows=out,
                pct_key="base_pct",
                shares_key="base_shares",
                rcept_no=rcept_no,
                source_date=source_date,
            ),
            flattened_headers,
        )
    def _extract_ipo_holders(self, *, xml_text: str, rcept_no: str, source_date: date) -> list[dict[str, Any]]:
        section3_html = self._extract_section_block(
            xml_text=xml_text,
            start_patterns=[
                r"iii\.\s*유상증자\s*전후의?\s*주요주주\s*지분변동",
                r"iii\.\s*유상증자\s*전후\s*주요주주\s*지분변동",
                r"iii\.\s*유상증자\s*전후의?\s*주요주주\s*소유주식\s*변동",
                r"iii\.\s*유상증자\s*전후의?\s*최대주주등\s*소유주식\s*변동",
                r"유상증자\s*전후의?\s*주요주주\s*지분변동",
                r"유상증자\s*전후의?\s*주요주주\s*소유주식\s*변동",
                r"유상증자\s*전후의?\s*주요주주\s*지분\s*변동",
                r"유상증자\s*전후의?\s*최대주주등\s*지분변동",
                r"유상증자\s*전후.*주요주주",
            ],
            end_patterns=[
                r"iv\.",
                r"iv\.\s*증권교부일",
                r"iv\.\s*증자교부일",
                r"iv\.\s*증자교부일등",
            ],
        )
        if not section3_html:
            return []

        table = self._find_section3_table(section3_html)
        if not table:
            return []

        rows, flattened_headers = self._parse_ipo_holder_table(
            table=table,
            rcept_no=rcept_no,
            source_date=source_date,
        )

        if not rows:
            log(f"[DART][WARN] IPO header parse failed / headers={flattened_headers}", verbose=self.verbose)
        return rows

    # =========================================================
    # section VI
    # =========================================================
    def _extract_offering_price(self, *, xml_text: str) -> Optional[Decimal]:
        section6_html = self._extract_section_block(
            xml_text=xml_text,
            start_patterns=[r"vi\.\s*조달된\s*자금의\s*사용내역", r"조달된\s*자금의\s*사용내역"],
            end_patterns=[
                r"vii\.",
                r"vii\.\s*신주인수권증서\s*발행내역",
                r"vii\.\s*신주인수권증서발행내역",
                r"vii\.\s*실권주\s*처리내역",
                r"viii\.",
            ],
        )
        if not section6_html:
            return None

        table = self._find_section6_table(section6_html)
        if table:
            value = self._extract_offering_price_from_funds_table(table)
            if value is not None:
                return value

        return self._extract_offering_price_from_funds_section_text(section6_html)

    def _score_section6_table(self, rows: list[list[str]]) -> int:
        flat = " ".join(" ".join(row) for row in rows)
        score = 0

        if "발행가액" in flat:
            score += 6
        if "모집" in flat:
            score += 5
        if "주식구분" in flat:
            score += 3
        if "발행총액" in flat:
            score += 1
        if "수량" in flat or "수 량" in flat:
            score += 2

        num_count = len(re.findall(r"[0-9][0-9,]*", flat))
        score += min(num_count, 6)

        if len(rows) <= 2 and num_count == 0:
            score -= 10

        return score

    def _find_section6_table(self, section_html: str) -> Optional[list[list[str]]]:
        tables = self._extract_tables_with_html(section_html)
        if not tables:
            return None

        candidates: list[tuple[int, list[list[str]]]] = []
        for rows in tables:
            candidates.append((self._score_section6_table(rows), rows))
        candidates.sort(key=lambda x: x[0], reverse=True)

        if candidates:
            best_score, best_rows = candidates[0]
            flat = " ".join(" ".join(r) for r in best_rows)
            if best_score > 0 and "모집" in flat and re.search(r"[0-9][0-9,]*", flat):
                return best_rows

        for i in range(len(tables) - 1):
            a = tables[i]
            b = tables[i + 1]
            flat_a = " ".join(" ".join(r) for r in a)
            flat_b = " ".join(" ".join(r) for r in b)

            if "발행가액" not in flat_a:
                continue
            if "모집" not in flat_b:
                continue

            return a + b

        return candidates[0][1] if candidates and candidates[0][0] > 0 else None

    def _extract_offering_price_from_funds_table(self, table: list[list[str]]) -> Optional[Decimal]:
        flat_rows = [" ".join(self._normalize_cell(x) for x in row) for row in table]

        for line in flat_rows:
            if "모집" not in line:
                continue

            nums = re.findall(r"[0-9][0-9,]*", line)
            values: list[Decimal] = []
            for n in nums:
                v = to_decimal(n)
                if v is not None:
                    values.append(v)

            if len(values) >= 2:
                price = values[1]
                if Decimal("100") <= price < Decimal("1000000"):
                    return quant2(price)

        return None

    def _extract_offering_price_from_funds_section_text(self, section_html: str) -> Optional[Decimal]:
        plain = self._strip_tags(section_html)
        plain = re.sub(r"\s+", " ", plain)

        for m in re.finditer(r"모집.{0,200}", plain, flags=re.IGNORECASE):
            chunk = m.group(0)
            nums = re.findall(r"[0-9][0-9,]*", chunk)

            values: list[Decimal] = []
            for n in nums:
                v = to_decimal(n)
                if v is not None:
                    values.append(v)

            if len(values) >= 2:
                price = values[1]
                if Decimal("100") <= price < Decimal("1000000"):
                    return quant2(price)

        m = re.search(r"발행가액.{0,40}?([0-9][0-9,]{1,})", plain, flags=re.IGNORECASE)
        if m:
            value = to_decimal(m.group(1))
            if value is not None and Decimal("100") <= value < Decimal("1000000"):
                return quant2(value)

        return None

    # =========================================================
    # latest shareholder parse
    # =========================================================
    def _score_latest_table(self, rows: list[list[str]]) -> int:
        flat = " ".join(" ".join(row) for row in rows)
        score = 0
        if "주주" in flat or "성명" in flat:
            score += 3
        if "지분율" in flat or "%" in flat:
            score += 3
        if "주식수" in flat:
            score += 2
        if "변동" in flat or "보고" in flat:
            score += 1
        if len(rows) >= 3:
            score += 1
        return score

    def _extract_latest_major_shareholders(self, *, xml_text: str, rcept_no: str, source_date: date) -> list[dict[str, Any]]:
        tables = self._extract_tables_with_html(xml_text)
        scored = sorted(((self._score_latest_table(table), table) for table in tables), key=lambda x: x[0], reverse=True)

        for score, table in scored:
            if score < 5:
                continue
            rows = self._parse_holder_table_generic(table, mode="latest")
            if rows:
                return self._merge_holder_rows(
                    rows=rows,
                    pct_key="latest_pct",
                    shares_key="latest_shares",
                    rcept_no=rcept_no,
                    source_date=source_date,
                )
        return []

    def _parse_holder_table_generic(self, table: list[list[str]], *, mode: str) -> list[dict[str, Any]]:
        if len(table) < 2:
            return []

        normalized_rows = [[self._normalize_header_token(cell) for cell in row] for row in table]
        header_idx = None
        header: list[str] = []

        for idx, row in enumerate(normalized_rows[:5]):
            joined = " ".join(row)
            if "주주명" in joined or "PCT" in joined or "SHARES" in joined:
                header_idx = idx
                header = row
                break

        if header_idx is None:
            return []

        def find_header_index(candidates: tuple[str, ...]) -> Optional[int]:
            for idx, col in enumerate(header):
                if any(candidate in col for candidate in candidates):
                    return idx
            return None

        name_idx = find_header_index(("주주명",))
        stock_type_idx = find_header_index(("주식의종류", "주식종류", "STOCKTYPE"))
        pct_idx = find_header_index(("PCT",))
        shares_idx = find_header_index(("SHARES",))

        if name_idx is None or pct_idx is None:
            return []

        out: list[dict[str, Any]] = []
        for raw_row in table[header_idx + 1 :]:
            row = raw_row[:] + [""] * max(0, len(header) - len(raw_row))
            holder_name = normalize_text(row[name_idx]) if name_idx < len(row) else ""
            holder_role = normalize_text(row[stock_type_idx]) if stock_type_idx is not None and stock_type_idx < len(row) else None
            pct_value = self._to_decimal(row[pct_idx]) if pct_idx < len(row) else None
            shares_value = self._to_int(row[shares_idx]) if shares_idx is not None and shares_idx < len(row) else None

            if not holder_name:
                continue
            if self._looks_like_sum_row(holder_name):
                continue
            if pct_value is None and shares_value is None:
                continue

            if mode == "latest":
                out.append(
                    {
                        "holder_key": self._make_holder_key(holder_name),
                        "holder_name": holder_name,
                        "holder_role": holder_role,
                        "latest_pct": quant4(pct_value) or Decimal("0"),
                        "latest_shares": shares_value,
                    }
                )

        return out

    # =========================================================
    # merge
    # =========================================================
    def _merge_holder_rows(
        self,
        *,
        rows: list[dict[str, Any]],
        pct_key: str,
        shares_key: str,
        rcept_no: str,
        source_date: date,
    ) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}

        for row in rows:
            holder_key = row["holder_key"]
            if not holder_key:
                continue

            if holder_key not in merged:
                merged[holder_key] = {
                    "holder_key": holder_key,
                    "holder_name": row["holder_name"],
                    "holder_role": row.get("holder_role"),
                    pct_key: row.get(pct_key) or Decimal("0"),
                    shares_key: row.get(shares_key),
                    "source_rcept_no": rcept_no,
                    "source_date": source_date,
                }
                continue

            merged_row = merged[holder_key]
            merged_row[pct_key] = quant4(
                (merged_row.get(pct_key) or Decimal("0")) + (row.get(pct_key) or Decimal("0"))
            ) or Decimal("0")

            prev_shares = merged_row.get(shares_key)
            curr_shares = row.get(shares_key)
            if prev_shares is None:
                merged_row[shares_key] = curr_shares
            elif curr_shares is not None:
                merged_row[shares_key] = int(prev_shares) + int(curr_shares)

            if not merged_row.get("holder_role") and row.get("holder_role"):
                merged_row["holder_role"] = row["holder_role"]

        return list(merged.values())