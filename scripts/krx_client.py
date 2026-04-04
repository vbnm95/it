from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Optional

import requests

from settings import KRX_API_BASE, KRX_AUTH_KEY, REQUEST_RETRIES, REQUEST_TIMEOUT
from utils import KRXAPIError, log, normalize_stock_code, normalize_text, parse_date, sleep_retry, to_decimal, to_int


@dataclass(frozen=True)
class KRXBaseRow:
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
class KRXTradeRow:
    stock_code: str
    date: date
    open: Optional[Decimal]
    high: Optional[Decimal]
    low: Optional[Decimal]
    close: Optional[Decimal]
    volume: Optional[int]
    raw_payload: dict[str, Any]


class KRXClient:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.session = requests.Session()

    def _get_rows(self, endpoint: str, *, bas_dd: date) -> list[dict[str, Any]]:
        url = f"{KRX_API_BASE.rstrip('/')}/{endpoint}"
        last_error: Exception | None = None

        for attempt in range(1, REQUEST_RETRIES + 1):
            try:
                resp = self.session.get(
                    url,
                    params={"basDd": bas_dd.strftime("%Y%m%d")},
                    headers={"AUTH_KEY": KRX_AUTH_KEY},
                    timeout=REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                payload = resp.json()
                rows = payload.get("OutBlock_1") or []
                if not isinstance(rows, list):
                    return []
                return [r for r in rows if isinstance(r, dict)]
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < REQUEST_RETRIES:
                    sleep_retry(attempt)

        raise KRXAPIError(f"KRX 요청 실패: {endpoint} / {last_error}")

    def fetch_base_info(self, market: str, *, bas_dd: date) -> list[KRXBaseRow]:
        endpoint = "stk_isu_base_info" if market == "KOSPI" else "ksq_isu_base_info"
        rows = self._get_rows(endpoint, bas_dd=bas_dd)
        out: list[KRXBaseRow] = []

        for row in rows:
            stock_code = normalize_stock_code(row.get("ISU_SRT_CD"))
            listing_date = parse_date(row.get("LIST_DD"))
            company_name = normalize_text(row.get("ISU_ABBRV") or row.get("ISU_NM"))

            if not stock_code or not listing_date or not company_name:
                continue

            out.append(
                KRXBaseRow(
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

        log(f"[KRX] {market} base rows={len(out)}", verbose=self.verbose)
        return out

    def fetch_daily_trade(self, market: str, *, bas_dd: date) -> list[KRXTradeRow]:
        endpoint = "stk_bydd_trd" if market == "KOSPI" else "ksq_bydd_trd"
        rows = self._get_rows(endpoint, bas_dd=bas_dd)
        out: list[KRXTradeRow] = []

        for row in rows:
            stock_code = normalize_stock_code(row.get("ISU_SRT_CD") or row.get("ISU_CD"))
            if not stock_code:
                continue
            trade_date = parse_date(row.get("BAS_DD")) or bas_dd
            out.append(
                KRXTradeRow(
                    stock_code=stock_code,
                    date=trade_date,
                    open=to_decimal(row.get("TDD_OPNPRC")),
                    high=to_decimal(row.get("TDD_HGPRC")),
                    low=to_decimal(row.get("TDD_LWPRC")),
                    close=to_decimal(row.get("TDD_CLSPRC")),
                    volume=to_int(row.get("ACC_TRDVOL")),
                    raw_payload=row,
                )
            )

        log(f"[KRX] {market} trade {bas_dd.isoformat()} rows={len(out)}", verbose=self.verbose)
        return out