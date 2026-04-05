from __future__ import annotations

import argparse
from datetime import date

from dart_client import DARTClient
from db import (
    fetch_active_companies,
    finish_sync_run,
    get_conn,
    replace_shareholder_ipo_base,
    start_sync_run,
)
from utils import kst_today, log, parse_date


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IPO Trace IPO shareholder rebuild")
    parser.add_argument("--as-of", type=str, default=None)
    parser.add_argument("--stock-code", type=str, default=None)
    parser.add_argument("--verbose", action="store_true")
    return parser


def _run_company_savepoint(conn, savepoint_name: str, fn):
    with conn.cursor() as cur:
        cur.execute(f"SAVEPOINT {savepoint_name}")
    try:
        result = fn()
    except Exception:
        with conn.cursor() as cur:
            cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
            cur.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        raise
    else:
        with conn.cursor() as cur:
            cur.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        return result


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    bas_dd: date = parse_date(args.as_of) if args.as_of else kst_today()
    if bas_dd is None:
        raise SystemExit("잘못된 --as-of 형식입니다.")

    stock_code_filter = (args.stock_code or "").strip().upper() if args.stock_code else None
    dart = DARTClient(verbose=args.verbose)

    with get_conn(autocommit=False) as conn:
        sync_run_id = start_sync_run(conn, job_name="rebuild_shareholders", run_date=bas_dd)

        stats = {
            "target_companies": 0,
            "ipo_base_rebuilt": 0,
            "rebuilt_companies": 0,
            "errors": [],
        }

        try:
            companies = fetch_active_companies(conn, as_of=bas_dd)
            if stock_code_filter:
                companies = [c for c in companies if str(c["stock_code"]).upper() == stock_code_filter]

            stats["target_companies"] = len(companies)

            for idx, company in enumerate(companies, start=1):
                stock_code = str(company["stock_code"]).upper()
                company_name = company["company_name"]
                listing_date = company["listing_date"]
                company_id = str(company["id"])

                def _job():
                    result = {
                        "ipo_rebuilt": False,
                    }

                    ipo_snapshot = dart.fetch_ipo_snapshot(
                        stock_code=stock_code,
                        company_name=company_name,
                        listing_date=listing_date,
                    )
                    ipo_rows = ipo_snapshot.get("ipo_holders") or []
                    if ipo_rows:
                        replace_shareholder_ipo_base(conn, company_id=company_id, rows=ipo_rows)
                        result["ipo_rebuilt"] = True

                    return result

                try:
                    savepoint_name = f"sp_rebuild_{idx}"
                    result = _run_company_savepoint(conn, savepoint_name, _job)

                    if result["ipo_rebuilt"]:
                        stats["ipo_base_rebuilt"] += 1
                    stats["rebuilt_companies"] += 1

                    log(f"[REBUILD] {stock_code} {company_name}", verbose=args.verbose)

                except Exception as exc:  # noqa: BLE001
                    stats["errors"].append(
                        {
                            "stock_code": stock_code,
                            "company_name": company_name,
                            "error": str(exc),
                        }
                    )
                    log(f"[ERROR] {stock_code} {company_name} / {exc}", verbose=True)

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
                    stats=stats,
                    error_message=str(exc),
                )
                fail_conn.commit()
            raise


if __name__ == "__main__":
    main()