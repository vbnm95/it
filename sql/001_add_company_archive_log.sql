create table if not exists public.company_archive_log (
  id bigserial primary key,
  stock_code varchar(6) not null,
  company_name text not null,
  listing_date date not null,
  tracking_expires_at date,
  db_deleted_at timestamptz not null default now(),
  reason text not null default 'TRACKING_EXPIRED',
  created_at timestamptz not null default now()
);

create index if not exists idx_company_archive_log_deleted_at
  on public.company_archive_log(db_deleted_at desc);

create index if not exists idx_company_archive_log_stock_code
  on public.company_archive_log(stock_code);
