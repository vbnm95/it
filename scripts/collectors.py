from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from dart_client import DARTClient
from db import (
    archive_company,
    fetch_active_companies,
    fetch_company_map,
    fetch_expired_companies,
    rebuild_key_shareholder_latest_for_company,
    replace_shareholder_ipo_base,
    replace_shareholder_latest_raw,
    update_company_latest_disclosure_date,
    update_company_price_snapshot,
    upsert_company,
    upsert_disclosure,
    upsert_price_daily,
)
from krx_client import KRXClient
from rules import is_target_security
from settings import SEED_LOOKBACK_DAYS, TRACKING_YEARS, TRACK_MARKETS
from utils import calc_return_since_ipo, kst_today


def add_years_safe(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        # 2/29 보정
        return d.replace(month=2, day=28, year=d.year + years)


def collect_target_base_rows(*, krx: KRXClient, bas_dd: date) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for market in TRACK_MARKETS:
        rows = krx.fetch_base_info(market, bas_dd=bas_dd)
        for row in rows:
            if is_target_security(
                company_name=row.company_name,
                market_type=row.market_type,
                security_group=row.security_group,
                stock_cert_type=row.stock_cert_type,
                sector_name=row.sector_name,
            ):
                out.append(
                    {
                        "stock_code": row.stock_code,
                        "company_name": row.company_name,
                        "market_type": row.market_type,
                        "listing_date": row.listing_date,
                    }
                )
    return out


def seed_companies(conn, *, krx: KRXClient, dart: DARTClient, bas_dd: date, verbose: bool = False) -> dict[str, Any]:
    cutoff = bas_dd - timedelta(days=SEED_LOOKBACK_DAYS)
    corp_code_map = dart.fetch_corp_code_map()
    company_map = fetch_company_map(conn)
    base_rows = collect_target_base_rows(krx=krx, bas_dd=bas_dd)

    inserted = 0
    updated = 0

    trade_map: dict[str, Any] = {}
    for market in TRACK_MARKETS:
        for trade in krx.fetch_daily_trade(market, bas_dd=bas_dd):
            trade_map[trade.stock_code] = trade

    for row in base_rows:
        if not (cutoff <= row["listing_date"] <= bas_dd):
            continue

        stock_code = row["stock_code"]
        corp_code = corp_code_map.get(stock_code)
        offering_info = dart.fetch_offering_info(corp_code, listing_date=row["listing_date"]) if corp_code else {}
        trade = trade_map.get(stock_code)

        payload = {
            "stock_code": stock_code,
            "company_name": row["company_name"],
            "market_type": row["market_type"],
            "listing_date": row["listing_date"],
            "dart_corp_code": corp_code,
            "offering_price": offering_info.get("offering_price"),
            "offering_price_source": "DART_SECURITIES_ISSUANCE_RESULT" if offering_info.get("offering_price") is not None else None,
            "offering_price_source_rcept_no": offering_info.get("source_rcept_no"),
            "current_price": trade.close if trade else None,
            "current_price_date": trade.date if trade else None,
            "return_since_ipo": calc_return_since_ipo(offering_info.get("offering_price"), trade.close if trade else None),
            "latest_disclosure_date": None,
            "key_shareholders_change_pct": Decimal("0"),
            "tracking_started_at": kst_today(),
            "tracking_expires_at": add_years_safe(row["listing_date"], TRACKING_YEARS),
            "is_active": True,
        }

        is_new = stock_code not in company_map
        company_id = upsert_company(conn, payload=payload)

        ipo_holders = dart.fetch_ipo_holders(corp_code, listing_date=row["listing_date"]) if corp_code else []
        replace_shareholder_ipo_base(
            conn,
            company_id=company_id,
            rows=[
                {
                    "holder_key": h.holder_key,
                    "holder_name": h.holder_name,
                    "holder_role": h.holder_role,
                    "base_pct": h.base_pct,
                    "base_shares": h.base_shares,
                    "source_rcept_no": h.source_rcept_no,
                    "source_date": h.source_date,
                }
                for h in ipo_holders
            ],
        )

        if is_new:
            inserted += 1
        else:
            updated += 1

    return {
        "seed_cutoff": cutoff.isoformat(),
        "inserted_or_newly_detected": inserted,
        "updated_existing": updated,
    }


def add_new_listings(conn, *, krx: KRXClient, dart: DARTClient, bas_dd: date, lookback_days: int, verbose: bool = False) -> dict[str, Any]:
    start_date = bas_dd - timedelta(days=lookback_days)
    corp_code_map = dart.fetch_corp_code_map()
    company_map = fetch_company_map(conn)
    base_rows = collect_target_base_rows(krx=krx, bas_dd=bas_dd)

    trade_map: dict[str, Any] = {}
    for market in TRACK_MARKETS:
        for trade in krx.fetch_daily_trade(market, bas_dd=bas_dd):
            trade_map[trade.stock_code] = trade

    new_count = 0

    for row in base_rows:
        if not (start_date <= row["listing_date"] <= bas_dd):
            continue
        if row["stock_code"] in company_map:
            continue

        stock_code = row["stock_code"]
        corp_code = corp_code_map.get(stock_code)
        offering_info = dart.fetch_offering_info(corp_code, listing_date=row["listing_date"]) if corp_code else {}
        trade = trade_map.get(stock_code)

        payload = {
            "stock_code": stock_code,
            "company_name": row["company_name"],
            "market_type": row["market_type"],
            "listing_date": row["listing_date"],
            "dart_corp_code": corp_code,
            "offering_price": offering_info.get("offering_price"),
            "offering_price_source": "DART_SECURITIES_ISSUANCE_RESULT" if offering_info.get("offering_price") is not None else None,
            "offering_price_source_rcept_no": offering_info.get("source_rcept_no"),
            "current_price": trade.close if trade else None,
            "current_price_date": trade.date if trade else None,
            "return_since_ipo": calc_return_since_ipo(offering_info.get("offering_price"), trade.close if trade else None),
            "latest_disclosure_date": None,
            "key_shareholders_change_pct": Decimal("0"),
            "tracking_started_at": kst_today(),
            "tracking_expires_at": add_years_safe(row["listing_date"], TRACKING_YEARS),
            "is_active": True,
        }

        company_id = upsert_company(conn, payload=payload)

        ipo_holders = dart.fetch_ipo_holders(corp_code, listing_date=row["listing_date"]) if corp_code else []
        replace_shareholder_ipo_base(
            conn,
            company_id=company_id,
            rows=[
                {
                    "holder_key": h.holder_key,
                    "holder_name": h.holder_name,
                    "holder_role": h.holder_role,
                    "base_pct": h.base_pct,
                    "base_shares": h.base_shares,
                    "source_rcept_no": h.source_rcept_no,
                    "source_date": h.source_date,
                }
                for h in ipo_holders
            ],
        )

        new_count += 1

    return {
        "lookback_start": start_date.isoformat(),
        "lookback_end": bas_dd.isoformat(),
        "detected_new_listings": new_count,
    }


def sync_prices(conn, *, krx: KRXClient, bas_dd: date, price_days: int, verbose: bool = False) -> dict[str, Any]:
    from utils import business_days_back

    companies = fetch_active_companies(conn, as_of=bas_dd)
    if not companies:
        return {"companies": 0, "price_rows": 0}

    dates = business_days_back(bas_dd, price_days)
    all_trades: dict[tuple[str, date], dict[str, Any]] = {}

    for market in TRACK_MARKETS:
        for d in dates:
            rows = krx.fetch_daily_trade(market, bas_dd=d)
            all_trades[(market, d)] = {r.stock_code: r for r in rows}

    price_rows = 0

    for company in companies:
        latest_trade = None
        for d in dates:
            trade = all_trades.get((company["market_type"], d), {}).get(company["stock_code"])
            if not trade:
                continue

            upsert_price_daily(
                conn,
                company_id=str(company["id"]),
                row={
                    "date": trade.date,
                    "open": trade.open,
                    "high": trade.high,
                    "low": trade.low,
                    "close": trade.close,
                    "volume": trade.volume,
                },
            )
            latest_trade = trade
            price_rows += 1

        if latest_trade:
            update_company_price_snapshot(
                conn,
                company_id=str(company["id"]),
                current_price=latest_trade.close,
                current_price_date=latest_trade.date,
                return_since_ipo=calc_return_since_ipo(company.get("offering_price"), latest_trade.close),
            )

    return {"companies": len(companies), "price_rows": price_rows}


def sync_disclosures(conn, *, dart: DARTClient, bas_dd: date, disclosure_days: int, verbose: bool = False) -> dict[str, Any]:
    companies = fetch_active_companies(conn, as_of=bas_dd)
    start_date = bas_dd - timedelta(days=disclosure_days)
    total_rows = 0

    for company in companies:
        corp_code = company.get("dart_corp_code")
        if not corp_code:
            continue

        rows = dart.fetch_disclosures(corp_code, start_date=start_date, end_date=bas_dd)
        latest_dt = None

        for row in rows:
            upsert_disclosure(
                conn,
                company_id=str(company["id"]),
                rcept_no=row.rcept_no,
                rcept_dt=row.rcept_dt,
                report_nm=row.report_nm,
            )
            total_rows += 1
            if latest_dt is None or row.rcept_dt > latest_dt:
                latest_dt = row.rcept_dt

        if latest_dt:
            update_company_latest_disclosure_date(conn, company_id=str(company["id"]), latest_disclosure_date=latest_dt)

    return {"companies": len(companies), "disclosure_rows": total_rows}


def sync_latest_shareholders(conn, *, dart: DARTClient, bas_dd: date, verbose: bool = False) -> dict[str, Any]:
    companies = fetch_active_companies(conn, as_of=bas_dd)
    touched = 0

    for company in companies:
        corp_code = company.get("dart_corp_code")
        if not corp_code:
            continue

        latest_rows = dart.fetch_latest_holders(corp_code)
        replace_shareholder_latest_raw(
            conn,
            company_id=str(company["id"]),
            rows=[
                {
                    "holder_key": h.holder_key,
                    "holder_name": h.holder_name,
                    "holder_role": h.holder_role,
                    "latest_pct": h.latest_pct,
                    "latest_shares": h.latest_shares,
                    "source_rcept_no": h.source_rcept_no,
                    "source_date": h.source_date,
                }
                for h in latest_rows
            ],
        )
        rebuild_key_shareholder_latest_for_company(conn, company_id=str(company["id"]))
        touched += 1

    return {"companies": len(companies), "rebuild_target_companies": touched}


def purge_expired(conn, *, bas_dd: date) -> dict[str, Any]:
    rows = fetch_expired_companies(conn, as_of=bas_dd)
    for row in rows:
        archive_company(conn, company=row, deleted_on=bas_dd)
    return {"expired_companies": len(rows)}