# IPO Trace Collector (KIND 조건 반영본)

이번 버전 반영 사항:

- 추적 대상 시장: **KOSPI + KOSDAQ**
- 추적 대상 상장유형: **신규상장**
- 추적 대상 증권구분: **일반주권 중심**
  - `SECUGRP_NM(증권구분)`이 주권 계열이 아닌 항목 제외
  - ETF/ETN/ELW/리츠/인프라/수익증권/신주인수권/전환사채/교환사채 등 제외
  - `KIND_STKCERT_TP_NM(주식종류)`이 우선/전환/상환/종류주 계열이면 제외
- **스팩 제외**
  - `sector_name`에 `SPAC` 포함 시 제외
  - 회사명에 `스팩` 또는 `SPAC` 포함 시 제외
- `stock_code`는 항상 **6자리 문자열**로 정규화
- Python 수집기 내부 시간 계산은 **Asia/Seoul(KST)** 기준 사용

주의:
- Supabase `timestamptz`는 절대시간으로 저장되므로, SQL Editor 세션 타임존이 UTC면 9시간 느리게 보일 수 있습니다.
- 이 경우 `sql/003_set_session_timezone_kst.sql`을 먼저 실행한 뒤 조회하세요.

## 추천 폴더 구조

```text
it/
├─ .env.local
├─ scripts/
│  ├─ collector_it.py
│  ├─ check_schema.py
│  └─ requirements.txt
└─ sql/
   ├─ 001_add_company_archive_log.sql
   ├─ 002_truncate_data_keep_schema.sql
   └─ 003_set_session_timezone_kst.sql
```

## 실행 순서

### 1) 데이터만 비우기 (스키마 유지)
Supabase SQL Editor에서:

```sql
-- sql/002_truncate_data_keep_schema.sql
truncate table public.price_daily restart identity cascade;
truncate table public.disclosures restart identity cascade;
truncate table public.shareholder_filings_raw restart identity cascade;
truncate table public.key_shareholder_latest cascade;
truncate table public.sync_runs restart identity cascade;
truncate table public.company_archive_log restart identity cascade;
truncate table public.companies cascade;
```

### 2) 스키마 확인

```bash
cd scripts
python .\check_schema.py
```

### 3) 최초 seed 테스트

```bash
python .\collector_it.py seed --dry-run --limit 10 --verbose --as-of 20260330
```

### 4) 최초 seed 실제 실행

```bash
python .\collector_it.py seed --verbose --as-of 20260330
```

### 5) 매일 배치

```bash
python .\collector_it.py daily --price-days 1 --disclosure-days 7 --new-listing-lookback-days 7 --verbose
```

## KST로 조회 예시

```sql
set time zone 'Asia/Seoul';

select id, job_name, status, started_at, finished_at
from public.sync_runs
order by id desc
limit 20;
```
