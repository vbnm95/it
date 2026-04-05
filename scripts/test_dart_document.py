from __future__ import annotations

import argparse
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from html import unescape
from typing import Any, Optional
from xml.etree import ElementTree as ET

import requests

from settings import DART_API_BASE, DART_API_KEY, REQUEST_RETRIES, REQUEST_TIMEOUT
from utils import (
    DARTAPIError,
    dumps_pretty,
    normalize_holder_key,
    normalize_text,
    quant2,
    quant4,
    sleep_retry,
    to_decimal,
    to_int,
)


@dataclass(frozen=True)
class DebugParseResult:
    rcept_no: str
    offering_price: Optional[Decimal]
    ipo_holders: list[dict[str, Any]]
    section3_table_found: bool
    section6_table_found: bool
    section3_table_preview: list[list[str]]
    section6_table_preview: list[list[str]]
    flattened_headers: list[str]


class DartDocumentDebugger:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.session = requests.Session()

    # =========================================================
    # public
    # =========================================================
    def parse_document(self, rcept_no: str) -> DebugParseResult:
        xml_text = self._download_document_xml(rcept_no)

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

        section6_html = self._extract_section_block(
            xml_text=xml_text,
            start_patterns=[
                r"vi\.\s*조달된\s*자금의\s*사용내역",
                r"조달된\s*자금의\s*사용내역",
            ],
            end_patterns=[
                r"vii\.",
                r"vii\.\s*신주인수권증서\s*발행내역",
                r"vii\.\s*신주인수권증서발행내역",
                r"vii\.\s*실권주\s*처리내역",
                r"viii\.",
            ],
        )

        section3_table = self._find_section3_table(section3_html) if section3_html else None
        section6_table = self._find_section6_table(section6_html) if section6_html else None

        if section3_table:
            print("=" * 80)
            print("[DEBUG] SECTION III TABLE SELECTED")
            for i, row in enumerate(section3_table[:20]):
                print(f"[DEBUG][SECTION3][{i:02d}] {row}")
        else:
            print("=" * 80)
            print("[DEBUG] SECTION III TABLE NOT FOUND")

        ipo_holders: list[dict[str, Any]] = []
        flattened_headers: list[str] = []

        if section3_table:
            ipo_holders, flattened_headers = self._parse_ipo_holder_table(
                table=section3_table,
                rcept_no=rcept_no,
                source_date=None,
            )

        offering_price = None
        if section6_table:
            offering_price = self._extract_offering_price_from_funds_table(section6_table)

        if offering_price is None and section6_html:
            offering_price = self._extract_offering_price_from_funds_section_text(section6_html)

        return DebugParseResult(
            rcept_no=rcept_no,
            offering_price=offering_price,
            ipo_holders=ipo_holders,
            section3_table_found=section3_table is not None,
            section6_table_found=section6_table is not None,
            section3_table_preview=section3_table[:10] if section3_table else [],
            section6_table_preview=section6_table[:10] if section6_table else [],
            flattened_headers=flattened_headers,
        )

    # =========================================================
    # download
    # =========================================================
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
                    raise DARTAPIError(
                        f"DART document 응답 오류: {rcept_no} / {dart_error}"
                    )

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
        # XML/텍스트 처리에 방해되는 제어문자 제거
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
            v = int(m.group(1))
            return v if v >= 1 else 1
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

    def _extract_tables_with_html(self, xml_text: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for table_match in re.finditer(r"(?is)<table[^>]*>.*?</table>", xml_text):
            table_html = table_match.group(0)
            rows = self._parse_html_table(table_html)
            if rows:
                out.append(
                    {
                        "html": table_html,
                        "rows": rows,
                        "start": table_match.start(),
                        "end": table_match.end(),
                    }
                )
        return out

    # =========================================================
    # section III - scoring / selection
    # =========================================================
    def _score_section3_table(self, rows: list[list[str]]) -> int:
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

        candidates: list[tuple[int, list[list[str]]]] = []
        for item in tables:
            rows = item["rows"]
            score = self._score_section3_table(rows)
            candidates.append((score, rows))

        candidates.sort(key=lambda x: x[0], reverse=True)
        if not candidates or candidates[0][0] <= 0:
            return None
        return candidates[0][1]

    # =========================================================
    # section III - header normalize / flatten
    # =========================================================
    def _norm_header_token(self, value: str) -> str:
        text = normalize_text(value)
        text = text.replace(" ", "")
        text = text.replace("\n", "")
        text = text.replace("\xa0", "")

        text = text.replace("주주명(명칭)", "주주명")
        text = text.replace("성명", "주주명")
        text = text.replace("주식종류", "주식의종류")

        # before / after
        text = text.replace("공모전", "BEFORE")
        text = text.replace("증자전", "BEFORE")
        text = text.replace("공모후", "AFTER")
        text = text.replace("증자후", "AFTER")

        # shares / pct
        text = text.replace("소유주식수", "SHARES")
        text = text.replace("보유주식수", "SHARES")
        text = text.replace("주식수", "SHARES")

        text = text.replace("소유비율", "PCT")
        text = text.replace("지분율", "PCT")
        text = text.replace("%", "PCT")

        return text

    def _is_header_like_row(self, row: list[str]) -> bool:
        normalized_cells = [self._norm_header_token(x) for x in row if x]
        joined = " ".join(normalized_cells)

        if not joined:
            return False

        structural_tokens = (
            "구분",
            "주주명",
            "관계",
            "주식의종류",
            "BEFORE",
            "AFTER",
            "SHARES",
            "PCT",
        )

        score = 0
        for token in structural_tokens:
            if token in joined:
                score += 1

        num_count = len(re.findall(r"\d[\d,]*", joined))
        if num_count >= 2:
            return False

        return score >= 2

    def _find_header_row_count(self, table: list[list[str]], max_header_rows: int = 3) -> int:
        header_count = 0
        scan_limit = min(len(table), max_header_rows + 2)

        for i in range(scan_limit):
            row = table[i]
            if self._is_header_like_row(row):
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

    def _flatten_headers(self, table: list[list[str]], header_row_count: int) -> list[str]:
        max_cols = max(len(r) for r in table)
        header_rows: list[list[str]] = []

        for i in range(header_row_count):
            row = table[i] if i < len(table) else []
            padded = row + [""] * (max_cols - len(row))
            header_rows.append([self._norm_header_token(x) for x in padded])

        flattened: list[str] = []
        for c in range(max_cols):
            parts = [header_rows[r][c] for r in range(header_row_count) if header_rows[r][c]]
            merged = "".join(parts)
            flattened.append(self._canonicalize_flattened_header(merged))

        return flattened

    # =========================================================
    # debug
    # =========================================================
    def _debug_print_ipo_table(self, table: list[list[str]]) -> None:
        print("=" * 80)
        print("[DEBUG][IPO TABLE RAW]")
        for i, row in enumerate(table[:20]):
            print(f"ROW {i:02d}: {row}")

        if not table:
            print("[DEBUG] empty table")
            return

        max_cols = max(len(r) for r in table)
        print("=" * 80)
        print(f"[DEBUG] max_cols={max_cols}")

        for i, row in enumerate(table[:6]):
            padded = row + [""] * (max_cols - len(row))
            normalized = [self._normalize_cell(x) for x in padded]
            print(f"[DEBUG][PADDED {i:02d}] {normalized}")

    def _debug_header_detection(self, table: list[list[str]], header_row_count: int, flattened_headers: list[str]) -> None:
        if not table:
            print("[DEBUG] no table for header detection")
            return

        max_cols = max(len(r) for r in table)

        print("=" * 80)
        print("[DEBUG][HEADER SCAN]")
        print(f"[DEBUG] detected_header_rows={header_row_count}")

        for i in range(min(len(table), 6)):
            row = [self._normalize_cell(x) for x in table[i]] + [""] * (max_cols - len(table[i]))
            rown = [self._norm_header_token(x) for x in row]
            print(f"[DEBUG][H {i}] {rown}")

        print("=" * 80)
        print("[DEBUG][FLATTENED_HEADERS]")
        for i, h in enumerate(flattened_headers):
            print(f"{i}: {h}")

    # =========================================================
    # section III - parse
    # =========================================================
    def _looks_like_sum_row(self, holder_name: str) -> bool:
        text = holder_name.replace(" ", "")
        return text in {"소계", "합계", "계", "총계"}

    def _to_pct_decimal(self, value: str) -> Optional[Decimal]:
        raw = self._normalize_cell(value)
        raw = raw.replace("%", "").replace("％", "").strip()
        return to_decimal(raw)

    def _parse_ipo_holder_table(
        self,
        *,
        table: list[list[str]],
        rcept_no: str,
        source_date: Optional[date],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        print("=" * 80)
        print("[DEBUG] _parse_ipo_holder_table called")
        self._debug_print_ipo_table(table)

        if len(table) < 2:
            return [], []

        header_row_count = self._find_header_row_count(table, max_header_rows=3)
        flattened_headers = self._flatten_headers(table, header_row_count=header_row_count)
        self._debug_header_detection(table, header_row_count, flattened_headers)

        def find_idx(target: str) -> Optional[int]:
            for idx, header in enumerate(flattened_headers):
                if header == target:
                    return idx
            return None

        group_idx = find_idx("GROUP")
        name_idx = find_idx("HOLDER_NAME")
        stock_type_idx = find_idx("STOCK_TYPE")
        after_shares_idx = find_idx("AFTER_SHARES")
        after_pct_idx = find_idx("AFTER_PCT")

        if name_idx is None or after_shares_idx is None or after_pct_idx is None:
            return [], flattened_headers

        data_start = header_row_count
        print(f"[DEBUG] data_start={data_start}")

        out: list[dict[str, Any]] = []
        max_cols = max(len(r) for r in table)
        current_group: Optional[str] = None

        for raw_row in table[data_start:]:
            row = [self._normalize_cell(x) for x in raw_row] + [""] * (max_cols - len(raw_row))

            if all(not x for x in row):
                continue

            group_val = row[group_idx] if group_idx is not None and group_idx < len(row) else ""
            if group_val:
                current_group = group_val

            holder_name = row[name_idx] if name_idx < len(row) else ""
            stock_type = row[stock_type_idx] if stock_type_idx is not None and stock_type_idx < len(row) else ""
            after_shares_raw = row[after_shares_idx] if after_shares_idx < len(row) else ""
            after_pct_raw = row[after_pct_idx] if after_pct_idx < len(row) else ""

            print(
                f"[DEBUG][ROW_PARSE] "
                f"name={holder_name!r}, stock_type={stock_type!r}, "
                f"after_shares_raw={after_shares_raw!r}, after_pct_raw={after_pct_raw!r}"
            )

            if not holder_name:
                continue
            if self._looks_like_sum_row(holder_name):
                continue
            if holder_name.replace(" ", "") in {"주주명", "성명"}:
                continue
            if re.fullmatch(r"[\d,\.%]+", holder_name):
                continue

            base_shares = to_int(after_shares_raw)
            base_pct = self._to_pct_decimal(after_pct_raw)

            if base_pct is not None and base_pct > Decimal("1000") and base_shares is None:
                maybe_shares = to_int(after_pct_raw)
                maybe_pct = self._to_pct_decimal(after_shares_raw)
                if maybe_pct is not None and maybe_pct <= Decimal("100"):
                    base_shares = maybe_shares
                    base_pct = maybe_pct

            if base_shares is None and base_pct is None:
                continue

            out.append(
                {
                    "holder_key": normalize_holder_key(holder_name),
                    "holder_name": holder_name,
                    "holder_role": stock_type or None,
                    "base_pct": quant4(base_pct) or Decimal("0"),
                    "base_shares": base_shares,
                    "source_rcept_no": rcept_no,
                    "source_date": source_date,
                }
            )

        return (
            self._merge_same_holder_rows(
                rows=out,
                pct_key="base_pct",
                shares_key="base_shares",
            ),
            flattened_headers,
        )

    # =========================================================
    # section VI
    # =========================================================
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

        rows_list = [item["rows"] for item in tables]

        candidates: list[tuple[int, list[list[str]]]] = []
        for rows in rows_list:
            score = self._score_section6_table(rows)
            candidates.append((score, rows))
        candidates.sort(key=lambda x: x[0], reverse=True)

        if candidates:
            best_score, best_rows = candidates[0]
            flat = " ".join(" ".join(r) for r in best_rows)
            if best_score > 0 and "모집" in flat and re.search(r"[0-9][0-9,]*", flat):
                return best_rows

        for i in range(len(rows_list) - 1):
            a = rows_list[i]
            b = rows_list[i + 1]
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
    # merge
    # =========================================================
    def _merge_same_holder_rows(
        self,
        *,
        rows: list[dict[str, Any]],
        pct_key: str,
        shares_key: str,
    ) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}

        for row in rows:
            holder_key = row["holder_key"]
            if not holder_key:
                continue

            if holder_key not in merged:
                merged[holder_key] = row.copy()
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Debug DART document parser")
    parser.add_argument("--rcept-no", required=True, help="DART 접수번호")
    return parser


def main() -> None:
        parser = build_parser()
        args = parser.parse_args()

        debugger = DartDocumentDebugger(verbose=True)
        result = debugger.parse_document(args.rcept_no)

        print("=" * 80)
        print("RCEPT NO:", result.rcept_no)
        print("SECTION III TABLE FOUND:", result.section3_table_found)
        print("SECTION VI TABLE FOUND:", result.section6_table_found)
        print("OFFERING PRICE:", result.offering_price)
        print("=" * 80)

        print("[FLATTENED HEADERS]")
        print(dumps_pretty(result.flattened_headers))
        print("=" * 80)

        print("[SECTION III TABLE PREVIEW]")
        print(dumps_pretty(result.section3_table_preview))
        print("=" * 80)

        print("[IPO HOLDERS]")
        print(dumps_pretty(result.ipo_holders))
        print("=" * 80)

        print("[SECTION VI TABLE PREVIEW]")
        print(dumps_pretty(result.section6_table_preview))
        print("=" * 80)


if __name__ == "__main__":
    main()