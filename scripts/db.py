from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row

from settings import DATABASE_URL
from utils import DatabaseError, dumps_pretty


@contextmanager
def get_conn(autocommit: bool = False):
    if not DATABASE_URL:
        raise DatabaseError("DATABASE_URL 환경변수가 필요합니다.")
    conn = psycopg.connect(DATABASE_URL, autocommit=autocommit, row_factory=dict_row)
    with conn.cursor() as cur:
        cur.execute("set time zone 'Asia/Seoul'")
    try:
        yield conn
    finally:
        conn.close()


def start_sync_run(conn: psycopg.Connection, *, job_name: str, run_date: date) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into public.sync_runs (job_name, run_date, status, started_at)
            values (%s, %s, 'RUNNING', now())
            returning id
            """,
            (job_name, run_date),
        )
        return int(cur.fetchone()["id"])


def finish_sync_run(
    conn: psycopg.Connection,
    *,
    sync_run_id: int,
    status: str,
    stats: dict[str, Any],
    error_message: Optional[str] = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            update public.sync_runs
            set status = %s,
                finished_at = now(),
                stats = %s::jsonb,
                error_message = %s
            where id = %s
            """,
            (status, dumps_pretty(stats), error_message, sync_run_id),
        )


def fetch_company_map(conn: psycopg.Connection) -> dict[str, dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select id, stock_code, company_name, market_type, listing_date, dart_corp_code,
                   offering_price, current_price, current_price_date, tracking_started_at,
                   tracking_expires_at, is_active
            from public.companies
            """
        )
        rows = cur.fetchall()
    return {str(r["stock_code"]).zfill(6): r for r in rows}


def fetch_active_companies(conn: psycopg.Connection, *, as_of: date) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select *
            from public.companies
            where is_active = true
              and tracking_expires_at >= %s
            order by listing_date desc, stock_code asc
            """,
            (as_of,),
        )
        return list(cur.fetchall())


def fetch_expired_companies(conn: psycopg.Connection, *, as_of: date) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select *
            from public.companies
            where is_active = true
              and tracking_expires_at < %s
            order by tracking_expires_at asc
            """,
            (as_of,),
        )
        return list(cur.fetchall())


def upsert_company(conn: psycopg.Connection, payload: dict[str, Any]) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into public.companies (
              stock_code,
              company_name,
              market_type,
              listing_date,
              dart_corp_code,
              offering_price,
              offering_price_source,
              offering_price_source_rcept_no,
              current_price,
              current_price_date,
              return_since_ipo,
              latest_disclosure_date,
              key_shareholders_change_pct,
              tracking_started_at,
              tracking_expires_at,
              is_active
            )
            values (
              %(stock_code)s,
              %(company_name)s,
              %(market_type)s,
              %(listing_date)s,
              %(dart_corp_code)s,
              %(offering_price)s,
              %(offering_price_source)s,
              %(offering_price_source_rcept_no)s,
              %(current_price)s,
              %(current_price_date)s,
              %(return_since_ipo)s,
              %(latest_disclosure_date)s,
              %(key_shareholders_change_pct)s,
              %(tracking_started_at)s,
              %(tracking_expires_at)s,
              %(is_active)s
            )
            on conflict (stock_code) do update
            set company_name = excluded.company_name,
                market_type = excluded.market_type,
                listing_date = excluded.listing_date,
                dart_corp_code = coalesce(excluded.dart_corp_code, public.companies.dart_corp_code),
                offering_price = coalesce(public.companies.offering_price, excluded.offering_price),
                offering_price_source = coalesce(public.companies.offering_price_source, excluded.offering_price_source),
                offering_price_source_rcept_no = coalesce(public.companies.offering_price_source_rcept_no, excluded.offering_price_source_rcept_no),
                current_price = coalesce(excluded.current_price, public.companies.current_price),
                current_price_date = coalesce(excluded.current_price_date, public.companies.current_price_date),
                return_since_ipo = coalesce(excluded.return_since_ipo, public.companies.return_since_ipo),
                tracking_started_at = least(public.companies.tracking_started_at, excluded.tracking_started_at),
                tracking_expires_at = excluded.tracking_expires_at,
                is_active = true
            returning id
            """,
            payload,
        )
        return str(cur.fetchone()["id"])


def upsert_price_daily(conn: psycopg.Connection, *, company_id: str, row: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into public.price_daily (
              company_id, date, open, high, low, close, volume
            )
            values (%s, %s, %s, %s, %s, %s, %s)
            on conflict (company_id, date) do update
            set open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume
            """,
            (
                company_id,
                row["date"],
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume"],
            ),
        )


def update_company_price_snapshot(
    conn: psycopg.Connection,
    *,
    company_id: str,
    current_price: Optional[Decimal],
    current_price_date: Optional[date],
    return_since_ipo: Optional[Decimal],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            update public.companies
            set current_price = %s,
                current_price_date = %s,
                return_since_ipo = %s
            where id = %s
            """,
            (current_price, current_price_date, return_since_ipo, company_id),
        )


def replace_shareholder_ipo_base(conn: psycopg.Connection, *, company_id: str, rows: list[dict[str, Any]]) -> None:
    with conn.cursor() as cur:
        cur.execute("delete from public.shareholder_ipo_base where company_id = %s", (company_id,))
        for row in rows:
            cur.execute(
                """
                insert into public.shareholder_ipo_base (
                  company_id, holder_key, holder_name, holder_role,
                  base_pct, base_shares, source_rcept_no, source_date, source_type
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, 'DART_SECURITIES_ISSUANCE_RESULT')
                """,
                (
                    company_id,
                    row["holder_key"],
                    row["holder_name"],
                    row["holder_role"],
                    row["base_pct"],
                    row["base_shares"],
                    row["source_rcept_no"],
                    row["source_date"],
                ),
            )


def archive_company(conn: psycopg.Connection, *, company: dict[str, Any], deleted_on: date) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into public.company_archive_log (
              original_company_id, stock_code, company_name, listing_date,
              tracking_expires_at, db_deleted_at, reason
            )
            values (%s, %s, %s, %s, %s, %s, 'TRACKING_EXPIRED')
            """,
            (
                company["id"],
                company["stock_code"],
                company["company_name"],
                company["listing_date"],
                company["tracking_expires_at"],
                deleted_on,
            ),
        )
        cur.execute(
            """
            update public.companies
            set is_active = false
            where id = %s
            """,
            (company["id"],),
        )