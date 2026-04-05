from __future__ import annotations

import argparse
from datetime import date, timedelta
from typing import Any

from db import (
    fetch_active_companies,
    finish_sync_run,
    get_conn,
    start_sync_run,
    update_company_price_snapshot,
    upsert_price_daily,
)
from krx_client import KRXClient, KRXTradeRow
from utils import (
    calc_return_since_ipo,
    dumps_pretty,
    log,
    normalize_stock_code,
    parse_date,
    previous_business_day,
)


TRACK_MARKETS = ("KOSPI", "KOSDAQ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IPO Trace price history backfill")
    parser.add_argument("--as-of", type=str, default=None, help="기준일 (YYYY-MM-DD or YYYYMMDD)")
    parser.add_argument("--days", type=int, default=365, help="과거 적재 일수 (기본 365)")
    parser.add_argument("--stock-code", type=str, default=None, help="특정 종목만 백필")
    parser.add_argument("--verbose", action="store_true")
    return parser


def business_dates_between(start_date: date, end_date: date) -> list[date]:
    out: list[date] = []
    cur = start_date
    while cur <= end_date:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def fetch_trade_map_for_date(krx: KRXClient, *, target_date: date) -> dict[str, KRXTradeRow]:
    trade_map: dict[str, KRXTradeRow] = {}
    for market in TRACK_MARKETS:
        for row in krx.fetch_daily_trade(market, bas_dd=target_date):
            trade_map[row.stock_code] = row
    return trade_map


def run_with_savepoint(conn, savepoint_name: str, job):
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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    bas_dd: date = parse_date(args.as_of) if args.as_of else previous_business_day()
    if bas_dd is None:
        raise SystemExit("잘못된 --as-of 형식입니다.")

    backfill_days = max(int(args.days), 1)
    cutoff_date = bas_dd - timedelta(days=backfill_days)
    stock_code_filter = normalize_stock_code(args.stock_code) if args.stock_code else None

    krx = KRXClient(verbose=args.verbose)

    stats: dict[str, Any] = {
        "as_of": bas_dd.isoformat(),
        "cutoff_date": cutoff_date.isoformat(),
        "target_companies": 0,
        "dates": [],
        "price_rows_saved": 0,
        "snapshot_updated": 0,
        "snapshot_skipped_newer_existing": 0,
        "companies_with_prices": 0,
        "errors": [],
    }

    sync_run_id: int | None = None

    try:
        # sync_run 은 짧은 autocommit 연결로 먼저 생성
        with get_conn(autocommit=True) as conn:
            sync_run_id = start_sync_run(conn, job_name="backfill_price_history", run_date=bas_dd)

        # 대상 기업 조회도 짧게
        with get_conn(autocommit=True) as conn:
            companies = fetch_active_companies(conn, as_of=bas_dd)

        companies = [c for c in companies if c["listing_date"] <= bas_dd]
        if stock_code_filter:
            companies = [c for c in companies if str(c["stock_code"]).upper() == stock_code_filter]

        if not companies:
            stats["target_companies"] = 0
            if sync_run_id is not None:
                with get_conn(autocommit=True) as conn:
                    finish_sync_run(conn, sync_run_id=sync_run_id, status="SUCCESS", stats=stats, error_message=None)
            print(dumps_pretty(stats))
            return

        per_company_start: dict[str, date] = {}
        for company in companies:
            company_id = str(company["id"])
            per_company_start[company_id] = max(company["listing_date"], cutoff_date)

        global_start = min(per_company_start.values())
        dates = business_dates_between(global_start, bas_dd)

        stats["target_companies"] = len(companies)
        stats["dates"] = [d.isoformat() for d in dates]

        latest_trade_by_company: dict[str, KRXTradeRow] = {}

        # -------------------------------------------------
        # 날짜별로:
        # 1) KRX 시세 fetch
        # 2) 짧은 DB 연결로 저장 후 commit
        # -------------------------------------------------
        for target_date in dates:
            trade_map = fetch_trade_map_for_date(krx, target_date=target_date)

            for write_attempt in range(1, 3):
                try:
                    with get_conn(autocommit=False) as conn:
                        saved_count_for_date = 0
                        latest_for_date: dict[str, KRXTradeRow] = {}

                        for idx, company in enumerate(companies, start=1):
                            company_id = str(company["id"])
                            stock_code = str(company["stock_code"]).upper()

                            if target_date < per_company_start[company_id]:
                                continue

                            trade_row = trade_map.get(stock_code)
                            if not trade_row:
                                continue

                            def _job() -> bool:
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
                                return True

                            try:
                                run_with_savepoint(conn, f"sp_backfill_{target_date.strftime('%Y%m%d')}_{idx}", _job)
                                saved_count_for_date += 1

                                prev = latest_for_date.get(company_id)
                                if prev is None or trade_row.date > prev.date:
                                    latest_for_date[company_id] = trade_row

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
                                log(
                                    f"[ERROR][BACKFILL_PRICE] {stock_code} {company['company_name']} / "
                                    f"{target_date} / {exc}",
                                    verbose=True,
                                )

                        conn.commit()

                    stats["price_rows_saved"] += saved_count_for_date
                    for company_id, trade_row in latest_for_date.items():
                        prev = latest_trade_by_company.get(company_id)
                        if prev is None or trade_row.date > prev.date:
                            latest_trade_by_company[company_id] = trade_row
                    break

                except Exception as exc:  # noqa: BLE001
                    if write_attempt >= 2:
                        raise
                    log(
                        f"[WARN][RETRY][BACKFILL_DATE] {target_date.isoformat()} / {exc}",
                        verbose=True,
                    )

        stats["companies_with_prices"] = len(latest_trade_by_company)

        # -------------------------------------------------
        # 최신 스냅샷 업데이트도 별도 짧은 연결에서 처리
        # -------------------------------------------------
        for write_attempt in range(1, 3):
            try:
                with get_conn(autocommit=False) as conn:
                    for idx, company in enumerate(companies, start=1):
                        company_id = str(company["id"])
                        stock_code = str(company["stock_code"]).upper()
                        latest_trade = latest_trade_by_company.get(company_id)
                        if not latest_trade:
                            continue

                        existing_snapshot_date = company.get("current_price_date")
                        if existing_snapshot_date is not None and existing_snapshot_date > latest_trade.date:
                            stats["snapshot_skipped_newer_existing"] += 1
                            log(
                                f"[SKIP][SNAPSHOT] {stock_code} {company['company_name']} / "
                                f"existing={existing_snapshot_date} > backfill_latest={latest_trade.date}",
                                verbose=args.verbose,
                            )
                            continue

                        def _job() -> bool:
                            update_company_price_snapshot(
                                conn,
                                company_id=company_id,
                                current_price=latest_trade.close,
                                current_price_date=latest_trade.date,
                                return_since_ipo=calc_return_since_ipo(company.get("offering_price"), latest_trade.close),
                            )
                            return True

                        try:
                            run_with_savepoint(conn, f"sp_backfill_snapshot_{idx}", _job)
                            stats["snapshot_updated"] += 1
                        except Exception as exc:  # noqa: BLE001
                            stats["errors"].append(
                                {
                                    "stock_code": stock_code,
                                    "company_name": company["company_name"],
                                    "stage": "price_snapshot",
                                    "error": str(exc),
                                }
                            )
                            log(
                                f"[ERROR][BACKFILL_SNAPSHOT] {stock_code} {company['company_name']} / {exc}",
                                verbose=True,
                            )

                    conn.commit()
                break
            except Exception as exc:  # noqa: BLE001
                if write_attempt >= 2:
                    raise
                log(f"[WARN][RETRY][BACKFILL_SNAPSHOT] {exc}", verbose=True)

        if sync_run_id is not None:
            with get_conn(autocommit=True) as conn:
                finish_sync_run(conn, sync_run_id=sync_run_id, status="SUCCESS", stats=stats, error_message=None)

        print(dumps_pretty(stats))

    except Exception as exc:  # noqa: BLE001
        if sync_run_id is not None:
            try:
                with get_conn(autocommit=True) as conn:
                    finish_sync_run(
                        conn,
                        sync_run_id=sync_run_id,
                        status="FAILED",
                        stats=stats,
                        error_message=str(exc),
                    )
            except Exception:
                pass
        raise


if __name__ == "__main__":
    main()