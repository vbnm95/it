# IPO Trace

> **순수 공모를 통한 신규상장 기업만 추적하는 IPO 데이터 수집기 & 웹앱 프로젝트**

최근 상장 기업을 대상으로,  
**상장 후 주가 흐름 / 최근 공시 / IPO 당시 주요주주 명단 / 최신 주요주주 지분 변화**를 수집·정리하여  
DB에 적재하고 웹에서 탐색할 수 있도록 만드는 프로젝트입니다.

---

## ✨ 프로젝트 개요

IPO Trace는 단순히 “최근 상장 기업 전체”를 모으는 프로젝트가 아닙니다.  
**순수 공모를 통해 신규상장한 기업만 선별하여**, 상장 이후 어떤 흐름을 보였는지 구조적으로 추적하는 데 초점을 둡니다.

이 프로젝트는 다음과 같은 질문에 답할 수 있도록 설계되었습니다.

- 최근 1년 내 상장한 기업은 어떤 종목들인가?
- 상장 이후 주가 흐름은 어땠는가?
- IPO 당시 주요주주 구성은 어땠는가?
- 현재 주요주주 지분율은 얼마나 바뀌었는가?
- 최근 어떤 공시가 나왔는가?

---

## 🎯 핵심 운영 원칙

IPO Trace는 아래 원칙을 엄격하게 적용합니다.

### 1. 순수 공모 신규상장 기업만 추적
다음과 같은 케이스는 **수집 대상에서 제외**합니다.

- 스팩 / SPAC
- 리츠 / REIT
- ETF / ETN / ELW
- 선박투자 / 인프라투융자 / 인프라펀드
- 합병 / 합병등
- 분할 / 분할합병
- 주식교환 / 주식이전
- 재상장 / 우회상장
- 집합투자증권 / 수익증권 / 투자회사 계열

즉, 공시 제목에 `증권발행실적보고서`가 들어간다고 해서 모두 IPO로 인정하지 않고,  
**순수 공모형 신규상장으로 볼 수 있는 기업만 허용**합니다.

### 2. 가격 이력과 현재가를 분리 저장
- **과거 가격 이력** → `price_daily`
- **현재가 스냅샷 / 현재가 날짜 / 공모가 대비 수익률** → `companies`

### 3. 주요주주 변화는 IPO 기준선과 최신 snapshot 비교로 계산
- IPO 당시 주요주주 명단 → `shareholder_ipo_base`
- 최신 주요주주 snapshot → `shareholder_latest_raw`
- 비교 결과 → `key_shareholder_latest`

### 4. holder_role은 주식 종류만 저장
`holder_role`에는 복잡한 그룹/관계 정보 대신 **주식 종류만 저장**합니다.

예:
- `보통주`
- `우선주`

---

## 🧩 주요 기능

### 기업 seed 적재
최근 1년 내 상장 기업 중, 규칙에 맞는 대상만 선별하여 DB에 저장합니다.

### 일별 가격 수집
상장 이후 가격 이력을 `price_daily`에 누적 저장합니다.

### 공시 수집
최근 공시를 수집하여 기업별 공시 이력을 구성합니다.

### IPO 기준 주요주주 파싱
DART `증권발행실적보고서`를 기반으로 IPO 당시 주요주주 명단을 추출합니다.

### 최신 주요주주 snapshot 수집
대량보유보고 / 최대주주등소유주식변동신고서 등에서 최신 지분율 snapshot을 추출합니다.

### 주요주주 변화 계산
IPO 시점과 최신 snapshot을 비교하여 변화량을 계산합니다.

---

## 🏗 기술 스택

### Frontend
- Next.js
- TypeScript
- Tailwind CSS
- Recharts

### Backend / Data
- Python
- Supabase (Postgres)
- Psycopg

### External Data Sources
- KRX Open API
- OpenDART API

---

## 📦 프로젝트 구조

```text
scripts/
├─ seed_companies.py            # 최근 1년 신규상장 seed 적재
├─ daily_update.py              # 일별 업데이트 실행
├─ collectors.py                # 회사별 저장 로직
├─ dart_client.py               # DART 파싱 핵심 로직
├─ krx_client.py                # KRX API 연동
├─ rules.py                     # 대상 제외 규칙
├─ rebuild_shareholders.py      # 주요주주 데이터 재생성
├─ backfill_price_history.py    # 최근 1년 가격 백필
├─ db.py                        # DB 저장/조회 함수
├─ utils.py                     # 공통 유틸
└─ settings.py                  # 환경변수/설정값