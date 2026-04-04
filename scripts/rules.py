from __future__ import annotations

from utils import normalize_text


def is_target_security(
    *,
    company_name: str,
    market_type: str,
    security_group: str | None,
    stock_cert_type: str | None,
    sector_name: str | None,
) -> bool:
    if market_type not in ("KOSPI", "KOSDAQ"):
        return False

    name = normalize_text(company_name)
    group = normalize_text(security_group)
    cert = normalize_text(stock_cert_type)
    sector = normalize_text(sector_name)

    name_u = name.upper()
    group_u = group.upper()
    cert_u = cert.upper()
    sector_u = sector.upper()

    if "스팩" in name or "SPAC" in name_u or "SPAC" in sector_u:
        return False

    if group and "주권" not in group:
        return False

    blocked_group_keywords = [
        "ETF", "ETN", "ELW", "리츠", "REIT", "인프라", "수익증권",
        "선박투자", "신주인수권", "전환사채", "교환사채", "파생", "외국"
    ]
    if any(x in group_u for x in blocked_group_keywords):
        return False

    blocked_cert_keywords = [
        "우선", "전환", "상환", "신주인수권", "종류주"
    ]
    if any(x in cert_u for x in blocked_cert_keywords):
        return False

    return True