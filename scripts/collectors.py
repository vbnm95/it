from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from db import (
    archive_company,
    fetch_active_companies,
    fetch_company_map,
    fetch_expired_companies,
    replace_shareholder_ipo_base,
    update_company_price_snapshot,
    upsert_company,
    upsert_price_daily,
)
from krx_client import KRXBaseRow, KRXClient, KRXTradeRow
from rules import is_excluded_security, is_seed_target
from settings import TRACKING_YEARS
from utils import business_days_back, calc_return_since_ipo, log


TRACK_MARKETS = ("KOSPI", "KOSDAQ")


def _safe_tracking_expires_at(listing_date: date) -> date:
    try:
        return listing_date.replace(year=listing_date.year + TRACKING_YEARS)
    except ValueError:
        return listing_date + timedelta(days=365 * TRACKING_YEARS)


def _company_payload_from_row(
    *,
    row: KRXBaseRow,
    dart_snapshot: dict[str, Any],
    trade_row: KRXTradeRow | None,
) -> dict[str, Any]:
    current_price = trade_row.close if trade_row else None
    current_price_date = trade_row.date if trade_row else None
    offering_price = dart_snapshot.get("offering_price")
    return_since_ipo = calc_return_since_ipo(offering_price, current_price)

    return {
        "stock_code": row.stock_code,
        "company_name": row.company_name,
        "market_type": row.market_type,
        "listing_date": row.listing_date,
        "dart_corp_code": dart_snapshot.get("corp_code"),
        "offering_price": offering_price,
        "offering_price_source": dart_snapshot.get("offering_price_source"),
        "offering_price_source_rcept_no": dart_snapshot.get("offering_price_source_rcept_no"),
        "current_price": current_price,
        "current_price_date": current_price_date,
        "return_since_ipo": return_since_ipo,
        "latest_disclosure_date": None,
        "key_shareholders_change_pct": Decimal("0"),
        "tracking_started_at": row.listing_date,
        "tracking_expires_at": _safe_tracking_expires_at(row.listing_date),
        "is_active": True,
    }


def _fetch_base_rows(krx: KRXClient, *, bas_dd: date) -> list[KRXBaseRow]:
    rows: list[KRXBaseRow] = []
    for market in TRACK_MARKETS:
        rows.extend(krx.fetch_base_info(market, bas_dd=bas_dd))
    return rows


def _fetch_trade_maps_by_date(krx: KRXClient, *, dates: list[date]) -> dict[date, dict[str, KRXTradeRow]]:
    out: dict[date, dict[str, KRXTradeRow]] = {}
    for target_date in dates:
        trade_map: dict[str, KRXTradeRow] = {}
        for market in TRACK_MARKETS:
            for row in krx.fetch_daily_trade(market, bas_dd=target_date):
                trade_map[row.stock_code] = row
        out[target_date] = trade_map
    return out


def _run_with_savepoint(conn, savepoint_name: str, job):
    with conn.cursor() as cur:
        cur.execute(f"SAVEPOINT {savepoint_name}")
    try:
        result = job()
    except Exception:
        with conn.cursor() as cur:
            cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
        raise
    else:
        with conn.cursor() as cur:
            cur.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        return result


def _save_company_seed_bundle(
    conn,
    *,
    row: KRXBaseRow,
    dart,
    trade_row: KRXTradeRow | None,
    verbose: bool,
) -> dict[str, Any]:
    dart_snapshot = dart.fetch_ipo_snapshot(
        stock_code=row.stock_code,
        company_name=row.company_name,
        listing_date=row.listing_date,
    )

    if not dart_snapshot.get("ipo_filing"):
        return {"status": "skip_no_ipo_filing"}

    payload = _company_payload_from_row(
        row=row,
        dart_snapshot=dart_snapshot,
        trade_row=trade_row,
    )
    company_id = upsert_company(conn, payload=payload)

    if trade_row:
        upsert_price_daily(
            conn,
            company_id=company_id,
            row={
                "date": trade_row.date,
                "open": trade_row.open,
                "high": trade_row.high,
                "low": trade_row.low,
                "close": trade_row.close,
                "volume": trade_row.volume,
            },
        )
        update_company_price_snapshot(
            conn,
            company_id=company_id,
            current_price=trade_row.close,
            current_price_date=trade_row.date,
            return_since_ipo=calc_return_since_ipo(payload["offering_price"], trade_row.close),
        )

    ipo_holders = dart_snapshot.get("ipo_holders") or []
    if ipo_holders:
        replace_shareholder_ipo_base(conn, company_id=company_id, rows=ipo_holders)

    log(f"[SAVE][COMPANY] {row.stock_code} {row.company_name} / company_id={company_id}", verbose=verbose)

    return {
        "status": "saved",
        "company_id": company_id,
        "ipo_holders_count": len(ipo_holders),
    }


def seed_companies(conn, *, krx: KRXClient, dart, bas_dd: date, verbose: bool = False) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "base_rows_total": 0,
        "recent_rows": 0,
        "saved_companies": 0,
        "skipped_by_rules": 0,
        "skipped_no_ipo_filing": 0,
        "ipo_holders_saved_companies": 0,
        "price_rows_saved": 0,
        "archived_companies": 0,
        "errors": [],
    }

    for idx, company in enumerate(fetch_expired_companies(conn, as_of=bas_dd), start=1):
        def _archive_job() -> bool:
            archive_company(conn, company=company, deleted_on=bas_dd)
            return True

        try:
            _run_with_savepoint(conn, f"sp_archive_seed_{idx}", _archive_job)
            stats["archived_companies"] += 1
            log(f"[ARCHIVE] {company['stock_code']} {company['company_name']}", verbose=verbose)
        except Exception as exc:  # noqa: BLE001
            stats["errors"].append(
                {
                    "stock_code": str(company["stock_code"]),
                    "company_name": company["company_name"],
                    "stage": "archive",
                    "error": str(exc),
                }
            )

    base_rows = _fetch_base_rows(krx, bas_dd=bas_dd)
    trade_maps = _fetch_trade_maps_by_date(krx, dates=[bas_dd])
    today_trade_map = trade_maps.get(bas_dd, {})
    stats["base_rows_total"] = len(base_rows)

    for idx, row in enumerate(
        sorted(base_rows, key=lambda x: (x.listing_date, x.market_type, x.stock_code), reverse=True),
        start=1,
    ):
        ok, reason = is_seed_target(row, as_of=bas_dd)
        if not ok:
            stats["skipped_by_rules"] += 1
            log(f"[SKIP][RULE] {row.stock_code} {row.company_name} / {reason}", verbose=verbose)
            continue

        stats["recent_rows"] += 1

        def _job() -> dict[str, Any]:
            return _save_company_seed_bundle(
                conn,
                row=row,
                dart=dart,
                trade_row=today_trade_map.get(row.stock_code),
                verbose=verbose,
            )

        try:
            result = _run_with_savepoint(conn, f"sp_seed_{idx}", _job)

            if result["status"] == "skip_no_ipo_filing":
                stats["skipped_no_ipo_filing"] += 1
                continue

            stats["saved_companies"] += 1
            if today_trade_map.get(row.stock_code):
                stats["price_rows_saved"] += 1
            if result["ipo_holders_count"] > 0:
                stats["ipo_holders_saved_companies"] += 1

        except Exception as exc:  # noqa: BLE001
            stats["errors"].append(
                {
                    "stock_code": row.stock_code,
                    "company_name": row.company_name,
                    "stage": "seed_company",
                    "error": str(exc),
                }
            )
            log(f"[ERROR] {row.stock_code} {row.company_name} / {exc}", verbose=True)

    return stats


def add_new_listings(
    conn,
    *,
    krx: KRXClient,
    dart,
    bas_dd: date,
    lookback_days: int,
    verbose: bool = False,
) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "base_rows_total": 0,
        "candidate_rows": 0,
        "new_companies": 0,
        "skipped_existing": 0,
        "skipped_excluded": 0,
        "skipped_no_ipo_filing": 0,
        "ipo_holders_saved_companies": 0,
        "price_rows_saved": 0,
        "errors": [],
    }

    company_map = fetch_company_map(conn)
    lower_bound = bas_dd - timedelta(days=max(lookback_days, 1) - 1)
    base_rows = _fetch_base_rows(krx, bas_dd=bas_dd)
    trade_maps = _fetch_trade_maps_by_date(krx, dates=[bas_dd])
    today_trade_map = trade_maps.get(bas_dd, {})
    stats["base_rows_total"] = len(base_rows)

    for idx, row in enumerate(
        sorted(base_rows, key=lambda x: (x.listing_date, x.market_type, x.stock_code), reverse=True),
        start=1,
    ):
        if not (lower_bound <= row.listing_date <= bas_dd):
            continue

        excluded, reason = is_excluded_security(row)
        if excluded:
            stats["skipped_excluded"] += 1
            log(f"[SKIP][EXCLUDED] {row.stock_code} {row.company_name} / {reason}", verbose=verbose)
            continue

        stats["candidate_rows"] += 1
        if row.stock_code in company_map:
            stats["skipped_existing"] += 1
            continue

        def _job() -> dict[str, Any]:
            return _save_company_seed_bundle(
                conn,
                row=row,
                dart=dart,
                trade_row=today_trade_map.get(row.stock_code),
                verbose=verbose,
            )

        try:
            result = _run_with_savepoint(conn, f"sp_new_{idx}", _job)

            if result["status"] == "skip_no_ipo_filing":
                stats["skipped_no_ipo_filing"] += 1
                continue

            stats["new_companies"] += 1
            if today_trade_map.get(row.stock_code):
                stats["price_rows_saved"] += 1
            if result["ipo_holders_count"] > 0:
                stats["ipo_holders_saved_companies"] += 1

            company_map[row.stock_code] = {"id": result["company_id"], "stock_code": row.stock_code}

        except Exception as exc:  # noqa: BLE001
            stats["errors"].append(
                {
                    "stock_code": row.stock_code,
                    "company_name": row.company_name,
                    "stage": "new_listing",
                    "error": str(exc),
                }
            )
            log(f"[ERROR][NEW] {row.stock_code} {row.company_name} / {exc}", verbose=True)

    return stats


def sync_prices(
    conn,
    *,
    krx: KRXClient,
    bas_dd: date,
    price_days: int,
    verbose: bool = False,
) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "target_companies": 0,
        "dates": [],
        "price_rows_saved": 0,
        "snapshot_updated": 0,
        "errors": [],
    }

    companies = fetch_active_companies(conn, as_of=bas_dd)
    stats["target_companies"] = len(companies)
    dates = business_days_back(bas_dd, max(price_days, 1))
    stats["dates"] = [d.isoformat() for d in dates]
    trade_maps = _fetch_trade_maps_by_date(krx, dates=dates)

    latest_trade_by_company: dict[str, KRXTradeRow] = {}

    for target_date in dates:
        trade_map = trade_maps.get(target_date, {})
        for idx, company in enumerate(companies, start=1):
            stock_code = str(company["stock_code"])
            trade_row = trade_map.get(stock_code)
            if not trade_row:
                continue

            def _job() -> bool:
                upsert_price_daily(
                    conn,
                    company_id=str(company["id"]),
                    row={
                        "date": trade_row.date,
                        "open": trade_row.open,
                        "high": trade_row.high,
                        "low": trade_row.low,
                        "close": trade_row.close,
                        "volume": trade_row.volume,
                    },
                )
                return True

            try:
                _run_with_savepoint(conn, f"sp_price_{target_date.strftime('%Y%m%d')}_{idx}", _job)
                stats["price_rows_saved"] += 1
                prev = latest_trade_by_company.get(str(company["id"]))
                if prev is None or trade_row.date > prev.date:
                    latest_trade_by_company[str(company["id"])] = trade_row
            except Exception as exc:  # noqa: BLE001
                stats["errors"].append(
                    {
                        "stock_code": stock_code,
                        "company_name": company["company_name"],
                        "date": target_date.isoformat(),
                        "stage": "price_daily",
                        "error": str(exc),
                    }
                )

    for idx, company in enumerate(companies, start=1):
        latest_trade = latest_trade_by_company.get(str(company["id"]))
        if not latest_trade:
            continue

        def _job() -> bool:
            update_company_price_snapshot(
                conn,
                company_id=str(company["id"]),
                current_price=latest_trade.close,
                current_price_date=latest_trade.date,
                return_since_ipo=calc_return_since_ipo(company.get("offering_price"), latest_trade.close),
            )
            return True

        try:
            _run_with_savepoint(conn, f"sp_price_snapshot_{idx}", _job)
            stats["snapshot_updated"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["errors"].append(
                {
                    "stock_code": str(company["stock_code"]),
                    "company_name": company["company_name"],
                    "stage": "price_snapshot",
                    "error": str(exc),
                }
            )
            log(f"[ERROR][PRICE_SNAPSHOT] {company['stock_code']} {company['company_name']} / {exc}", verbose=True)

    return stats


def purge_expired(conn, *, bas_dd: date) -> dict[str, Any]:
    stats = {"archived_companies": 0, "errors": []}

    expired = fetch_expired_companies(conn, as_of=bas_dd)
    for idx, company in enumerate(expired, start=1):
        def _job() -> bool:
            archive_company(conn, company=company, deleted_on=bas_dd)
            return True

        try:
            _run_with_savepoint(conn, f"sp_archive_daily_{idx}", _job)
            stats["archived_companies"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["errors"].append(
                {
                    "stock_code": str(company["stock_code"]),
                    "company_name": company["company_name"],
                    "stage": "purge_expired",
                    "error": str(exc),
                }
            )

    return stats