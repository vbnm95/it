begin;

create extension if not exists pgcrypto;

-- =========================================================
-- 기존 객체 정리
-- =========================================================

drop view if exists public.v_companies_display;

drop table if exists public.company_archive_log cascade;
drop table if exists public.sync_runs cascade;
drop table if exists public.key_shareholder_latest cascade;
drop table if exists public.shareholder_latest_raw cascade;
drop table if exists public.shareholder_ipo_base cascade;
drop table if exists public.disclosures cascade;
drop table if exists public.price_daily cascade;
drop table if exists public.companies cascade;

drop function if exists public.set_updated_at cascade;

drop type if exists public.offering_price_source_type cascade;
drop type if exists public.shareholder_source_type cascade;
drop type if exists public.sync_status cascade;
drop type if exists public.market_type cascade;

-- =========================================================
-- ENUM TYPES
-- =========================================================

create type public.market_type as enum ('KOSPI', 'KOSDAQ');

create type public.sync_status as enum ('RUNNING', 'SUCCESS', 'FAILED');

-- shareholder_ipo_base 호환성을 위해 기존 enum 유지
create type public.shareholder_source_type as enum (
  'DART_SECURITIES_ISSUANCE_RESULT',
  'DART_MAJORSTOCK'
);

create type public.offering_price_source_type as enum (
  'DART_SECURITIES_ISSUANCE_RESULT',
  'KIND_FALLBACK',
  'MANUAL'
);

-- =========================================================
-- updated_at trigger helper
-- =========================================================

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- =========================================================
-- companies
-- =========================================================
-- 프론트/기존 코드 호환성을 위해 기존 컬럼 구조 유지
-- latest_disclosure_date / key_shareholders_change_pct 는 현재 미사용 예정이지만 남겨둠

create table public.companies (
  id uuid primary key default gen_random_uuid(),

  stock_code varchar(9) not null unique,
  company_name text not null,
  market_type public.market_type not null,

  listing_date date not null,
  dart_corp_code varchar(8),

  offering_price numeric(18,2),
  offering_price_source public.offering_price_source_type,
  offering_price_source_rcept_no varchar(20),

  current_price numeric(18,2),
  current_price_date date,
  return_since_ipo numeric(18,2),

  latest_disclosure_date date,
  key_shareholders_change_pct numeric(18,4) not null default 0,

  tracking_started_at date not null,
  tracking_expires_at date not null,
  is_active boolean not null default true,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint companies_stock_code_format_chk
    check (stock_code ~ '^[0-9A-Z]{6,9}$'),

  constraint companies_tracking_period_chk
    check (tracking_expires_at >= tracking_started_at)
);

create index idx_companies_is_active_listing_date
  on public.companies (is_active, listing_date desc);

create index idx_companies_market_type
  on public.companies (market_type);

create index idx_companies_tracking_expires_at
  on public.companies (tracking_expires_at);

create index idx_companies_latest_disclosure_date
  on public.companies (latest_disclosure_date desc);

create trigger trg_companies_updated_at
before update on public.companies
for each row
execute function public.set_updated_at();

-- =========================================================
-- price_daily
-- =========================================================

create table public.price_daily (
  id bigserial primary key,

  company_id uuid not null references public.companies(id) on delete cascade,
  date date not null,
  open numeric(18,2),
  high numeric(18,2),
  low numeric(18,2),
  close numeric(18,2) not null,
  volume bigint,

  created_at timestamptz not null default now(),

  constraint price_daily_company_date_uniq unique (company_id, date)
);

create index idx_price_daily_company_date
  on public.price_daily (company_id, date desc);

create index idx_price_daily_date
  on public.price_daily (date desc);

-- =========================================================
-- shareholder_ipo_base
-- =========================================================
-- IPO 당시 주요주주 기준선만 유지

create table public.shareholder_ipo_base (
  id bigserial primary key,

  company_id uuid not null references public.companies(id) on delete cascade,
  holder_key text not null,
  holder_name text not null,
  holder_role text,
  base_pct numeric(18,4) not null default 0,
  base_shares numeric(20,0),
  source_rcept_no varchar(20),
  source_date date,
  source_type public.shareholder_source_type not null default 'DART_SECURITIES_ISSUANCE_RESULT',

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint shareholder_ipo_base_company_holder_uniq
    unique (company_id, holder_key)
);

create index idx_shareholder_ipo_base_company
  on public.shareholder_ipo_base (company_id);

create trigger trg_shareholder_ipo_base_updated_at
before update on public.shareholder_ipo_base
for each row
execute function public.set_updated_at();

-- =========================================================
-- sync_runs
-- =========================================================

create table public.sync_runs (
  id bigserial primary key,

  job_name text not null,
  run_date date not null,
  status public.sync_status not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  stats jsonb,
  error_message text,

  created_at timestamptz not null default now()
);

create index idx_sync_runs_job_run_date
  on public.sync_runs (job_name, run_date desc);

create index idx_sync_runs_status
  on public.sync_runs (status);

-- =========================================================
-- company_archive_log
-- =========================================================

create table public.company_archive_log (
  id bigserial primary key,

  original_company_id uuid,
  stock_code varchar(9) not null,
  company_name text not null,
  listing_date date not null,
  tracking_expires_at date not null,
  db_deleted_at date not null,
  reason text not null default 'TRACKING_EXPIRED',

  created_at timestamptz not null default now()
);

create index idx_company_archive_log_stock_code
  on public.company_archive_log (stock_code);

create index idx_company_archive_log_deleted_at
  on public.company_archive_log (db_deleted_at desc);

-- =========================================================
-- 화면용 view
-- =========================================================
-- view 이름과 컬럼도 기존과 동일하게 유지

create view public.v_companies_display as
select
  c.id,
  c.stock_code,
  c.company_name,
  c.market_type,
  c.listing_date,
  c.offering_price,
  c.current_price,
  c.current_price_date,
  c.return_since_ipo,
  c.latest_disclosure_date,
  c.key_shareholders_change_pct,
  c.tracking_started_at,
  c.tracking_expires_at,
  c.is_active
from public.companies c
where c.is_active = true
  and c.listing_date >= (current_date - interval '1 year');

commit;