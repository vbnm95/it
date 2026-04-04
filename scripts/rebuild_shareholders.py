from __future__ import annotations

import argparse

from db import fetch_active_companies, get_conn, rebuild_key_shareholder_latest_for_company
from utils import dumps_pretty, parse_date, previous_business_day


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IPO Trace rebuild shareholders")
    parser.add_argument("--as-of", dest="as_of", help="YYYY-MM-DD or YYYYMMDD")
    parser.add_argument("--stock-code", dest="stock_code", help="특정 종목코드만 재계산")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bas_dd = parse_date(args.as_of) if args.as_of else previous_business_day()
    if not bas_dd:
        raise RuntimeError("잘못된 날짜 형식입니다.")

    rebuilt = 0

    with get_conn(autocommit=False) as conn:
        companies = fetch_active_companies(conn, as_of=bas_dd)

        if args.stock_code:
            companies = [c for c in companies if c["stock_code"] == str(args.stock_code).zfill(6)]

        for company in companies:
            rebuild_key_shareholder_latest_for_company(conn, company_id=str(company["id"]))
            rebuilt += 1

        conn.commit()

    print(dumps_pretty({"rebuilt_companies": rebuilt}))


if __name__ == "__main__":
    main()