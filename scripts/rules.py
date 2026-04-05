from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
from typing import Any, Optional

from krx_client import KRXBaseRow
from settings import SEED_LOOKBACK_DAYS
from utils import normalize_text


EXCLUDE_NAME_KEYWORDS = (
    "스팩",
    "SPAC",
    "리츠",
    "REIT",
)

EXCLUDE_SECURITY_GROUP_KEYWORDS = (
    "스팩",
    "리츠",
    "ETF",
    "ETN",
    "ELW",
    "선박투자",
    "인프라투융자",
    "인프라펀드",
)

EXCLUDE_STOCK_CERT_TYPE_KEYWORDS = (
    "수익증권",
    "투자회사",
    "리츠",
    "상장지수",
    "선박투자",
    "인프라",
)

PREFERRED_REPORT_NAMES = (
    "증권발행실적보고서",
)


def row_to_dict(row: KRXBaseRow) -> dict[str, Any]:
    return asdict(row)


def _contains_any(value: Optional[str], keywords: tuple[str, ...]) -> bool:
    text = normalize_text(value).upper()
    return any(keyword.upper() in text for keyword in keywords)


def is_recent_listing(row: KRXBaseRow, *, as_of: date) -> bool:
    lower_bound = as_of - timedelta(days=SEED_LOOKBACK_DAYS)
    return lower_bound <= row.listing_date <= as_of


def is_excluded_security(row: KRXBaseRow) -> tuple[bool, Optional[str]]:
    if _contains_any(row.company_name, EXCLUDE_NAME_KEYWORDS):
        return True, "company_name_excluded"

    if _contains_any(row.security_group, EXCLUDE_SECURITY_GROUP_KEYWORDS):
        return True, "security_group_excluded"

    if _contains_any(row.stock_cert_type, EXCLUDE_STOCK_CERT_TYPE_KEYWORDS):
        return True, "stock_cert_type_excluded"

    return False, None


def is_seed_target(row: KRXBaseRow, *, as_of: date) -> tuple[bool, str]:
    if not is_recent_listing(row, as_of=as_of):
        return False, "listing_date_out_of_range"

    excluded, reason = is_excluded_security(row)
    if excluded:
        return False, reason or "excluded_security"

    return True, "ok"