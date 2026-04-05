from __future__ import annotations

import argparse
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional
from xml.etree import ElementTree as ET

import requests

from settings import DART_API_BASE, DART_API_KEY, REQUEST_RETRIES, REQUEST_TIMEOUT
from utils import DARTAPIError, dumps_pretty, normalize_stock_code, normalize_text, parse_date, sleep_retry


@dataclass(frozen=True)
class DartFiling:
    rcept_no: str
    report_nm: str
    rcept_dt: date


class DARTFinder:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.session = requests.Session()
        self._corp_code_by_stock_code: dict[str, str] | None = None
        self._corp_name_by_stock_code: dict[str, str] | None = None

    def resolve_corp_code(self, stock_code: str) -> Optional[str]:
        self._ensure_corp_codes()
        assert self._corp_code_by_stock_code is not None
        return self._corp_code_by_stock_code.get(stock_code)

    def search_ipo_filings(
        self,
        *,
        stock_code: str,
        listing_date: date,
    ) -> dict[str, Any]:
        corp_code = self.resolve_corp_code(stock_code)
        if not corp_code:
            return {
                "stock_code": stock_code,
                "corp_code": None,
                "candidates": [],
            }

        filings = self._list_filings(
            corp_code=corp_code,
            begin_date=listing_date - timedelta(days=180),
            end_date=listing_date + timedelta(days=30),
            page_count=100,
        )

        candidates = []
        for filing in filings:
            if "증권발행실적보고서" not in filing.report_nm:
                continue

            candidates.append(
                {
                    "rcept_no": filing.rcept_no,
                    "report_nm": filing.report_nm,
                    "rcept_dt": filing.rcept_dt.isoformat(),
                    "distance_from_listing_days": abs((filing.rcept_dt - listing_date).days),
                }
            )

        candidates.sort(
            key=lambda x: (
                x["distance_from_listing_days"],
                -int(x["rcept_dt"].replace("-", "")),
                -int(x["rcept_no"]),
            )
        )

        return {
            "stock_code": stock_code,
            "corp_code": corp_code,
            "candidates": candidates,
        }

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

                with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                    xml_names = [name for name in zf.namelist() if name.lower().endswith(".xml")]
                    if not xml_names:
                        raise DARTAPIError("ZIP 내부 XML 없음")

                    with zf.open(xml_names[0]) as fp:
                        root = ET.parse(fp).getroot()

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
                    if status == "013":
                        return {"list": []}
                    raise DARTAPIError(f"{endpoint} / status={status} / {payload.get('message')}")

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Find IPO securities issuance filings")
    parser.add_argument("--stock-code", required=True, help="종목코드 (예: 005930, 0088M0, A0088M0)")
    parser.add_argument("--listing-date", required=True, help="상장일 YYYY-MM-DD 또는 YYYYMMDD")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    stock_code = normalize_stock_code(args.stock_code)
    if not stock_code:
        raise SystemExit("잘못된 --stock-code 입니다. 숫자/영문 종목코드를 입력해야 합니다.")

    listing_date = parse_date(args.listing_date)
    if listing_date is None:
        raise SystemExit("잘못된 --listing-date 입니다.")

    finder = DARTFinder(verbose=True)
    result = finder.search_ipo_filings(
        stock_code=stock_code,
        listing_date=listing_date,
    )

    print(dumps_pretty(result))


if __name__ == "__main__":
    main()