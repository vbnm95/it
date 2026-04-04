from __future__ import annotations

import argparse

from collectors import add_new_listings, purge_expired, sync_disclosures, sync_latest_shareholders, sync_prices
from dart_client import DARTClient
from db import finish_sync_run, get_conn, start_sync_run
from krx_client import KRXClient
from settings import DISCLOSURE_DAYS, NEW_LISTING_LOOKBACK_DAYS, PRICE_DAYS
from utils import dumps_pretty, parse_date, previous_business_day


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IPO Trace daily update")
    parser.add_argument("--as-of", dest="as_of", help="YYYY-MM-DD or YYYYMMDD")
    parser.add_argument("--price-days", type=int, default=PRICE_DAYS)
    parser.add_argument("--disclosure-days", type=int, default=DISCLOSURE_DAYS)
    parser.add_argument("--new-listing-lookback-days", type=int, default=NEW_LISTING_LOOKBACK_DAYS)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bas_dd = parse_date(args.as_of) if args.as_of else previous_business_day()
    if not bas_dd:
        raise RuntimeError("잘못된 날짜 형식입니다.")

    krx = KRXClient(verbose=args.verbose)
    dart = DARTClient(verbose=args.verbose)

    with get_conn(autocommit=False) as conn:
        sync_run_id = start_sync_run(conn, job_name="daily", run_date=bas_dd)
        try:
            stats = {
                "new_listings": add_new_listings(
                    conn,
                    krx=krx,
                    dart=dart,
                    bas_dd=bas_dd,
                    lookback_days=args.new_listing_lookback_days,
                    verbose=args.verbose,
                ),
                "prices": sync_prices(
                    conn,
                    krx=krx,
                    bas_dd=bas_dd,
                    price_days=args.price_days,
                    verbose=args.verbose,
                ),
                "disclosures": sync_disclosures(
                    conn,
                    dart=dart,
                    bas_dd=bas_dd,
                    disclosure_days=args.disclosure_days,
                    verbose=args.verbose,
                ),
                "shareholders": sync_latest_shareholders(
                    conn,
                    dart=dart,
                    bas_dd=bas_dd,
                    verbose=args.verbose,
                ),
                "purge": purge_expired(conn, bas_dd=bas_dd),
            }
            finish_sync_run(conn, sync_run_id=sync_run_id, status="SUCCESS", stats=stats)
            conn.commit()
            print(dumps_pretty(stats))
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            with get_conn(autocommit=True) as log_conn:
                finish_sync_run(log_conn, sync_run_id=sync_run_id, status="FAILED", stats={}, error_message=str(exc))
            raise


if __name__ == "__main__":
    main()