from __future__ import annotations

import argparse

from collectors import seed_companies
from dart_client import DARTClient
from db import finish_sync_run, get_conn, start_sync_run
from krx_client import KRXClient
from utils import dumps_pretty, parse_date, previous_business_day


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IPO Trace seed companies")
    parser.add_argument("--as-of", dest="as_of", help="YYYY-MM-DD or YYYYMMDD")
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
        sync_run_id = start_sync_run(conn, job_name="seed", run_date=bas_dd)
        try:
            stats = seed_companies(conn, krx=krx, dart=dart, bas_dd=bas_dd, verbose=args.verbose)
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