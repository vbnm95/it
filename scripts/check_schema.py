from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=False)
load_dotenv(BASE_DIR / ".env.local", override=False)
load_dotenv(override=False)

DATABASE_URL = os.getenv("DATABASE_URL")
REQUIRED_TABLES = [
    "companies",
    "price_daily",
    "disclosures",
    "shareholder_filings_raw",
    "key_shareholder_latest",
    "sync_runs",
]
OPTIONAL_TABLES = ["company_archive_log"]


def main() -> None:
    if not DATABASE_URL:
        raise SystemExit("DATABASE_URL 환경변수가 없습니다.")

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select table_name
            from information_schema.tables
            where table_schema = 'public'
            order by table_name
            """
        )
        tables = {row["table_name"] for row in cur.fetchall()}

        print("[tables]")
        for name in sorted(tables):
            print(" -", name)

        print("\n[required]")
        for name in REQUIRED_TABLES:
            print(f" - {name}: {'OK' if name in tables else 'MISSING'}")

        print("\n[optional]")
        for name in OPTIONAL_TABLES:
            print(f" - {name}: {'OK' if name in tables else 'MISSING'}")

        if "company_archive_log" in tables:
            cur.execute(
                """
                select column_name, data_type
                from information_schema.columns
                where table_schema = 'public'
                  and table_name = 'company_archive_log'
                order by ordinal_position
                """
            )
            print("\n[company_archive_log columns]")
            for row in cur.fetchall():
                print(f" - {row['column_name']} ({row['data_type']})")


if __name__ == "__main__":
    main()
