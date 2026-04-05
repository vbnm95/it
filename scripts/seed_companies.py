from __future__ import annotations

import argparse
from datetime import date

from collectors import seed_companies
from dart_client import DARTClient
from db import finish_sync_run, get_conn, start_sync_run
from krx_client import KRXClient
from utils import kst_today, parse_date


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IPO Trace companies seed")
    parser.add_argument(
        "--as-of",
        type=str,
        default=None,
        help="기준일 (YYYY-MM-DD or YYYYMMDD). 기본값: 오늘(KST)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="상세 로그 출력",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    bas_dd: date = parse_date(args.as_of) if args.as_of else kst_today()
    if bas_dd is None:
        raise SystemExit("잘못된 --as-of 형식입니다.")

    krx = KRXClient(verbose=args.verbose)
    dart = DARTClient(verbose=args.verbose)

    with get_conn(autocommit=False) as conn:
        sync_run_id = start_sync_run(conn, job_name="seed_companies", run_date=bas_dd)

        try:
            stats = seed_companies(
                conn,
                krx=krx,
                dart=dart,
                bas_dd=bas_dd,
                verbose=args.verbose,
            )
            finish_sync_run(
                conn,
                sync_run_id=sync_run_id,
                status="SUCCESS",
                stats=stats,
                error_message=None,
            )
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            with get_conn(autocommit=False) as fail_conn:
                finish_sync_run(
                    fail_conn,
                    sync_run_id=sync_run_id,
                    status="FAILED",
                    stats={},
                    error_message=str(exc),
                )
                fail_conn.commit()
            raise


if __name__ == "__main__":
    main()