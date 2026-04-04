from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]

load_dotenv(BASE_DIR / ".env", override=False)
load_dotenv(BASE_DIR / ".env.local", override=False)
load_dotenv(override=False)

DATABASE_URL = os.getenv("DATABASE_URL", "")
KRX_AUTH_KEY = os.getenv("KRX_AUTH_KEY", "")
DART_API_KEY = os.getenv("DART_API_KEY", "")

KRX_API_BASE = os.getenv("KRX_API_BASE", "https://data-dbg.krx.co.kr/svc/apis/sto")
DART_API_BASE = os.getenv("DART_API_BASE", "https://opendart.fss.or.kr/api")

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
REQUEST_RETRIES = int(os.getenv("REQUEST_RETRIES", "3"))

TRACK_MARKETS = ("KOSPI", "KOSDAQ")
SEED_LOOKBACK_DAYS = int(os.getenv("SEED_LOOKBACK_DAYS", "365"))
TRACKING_YEARS = int(os.getenv("TRACKING_YEARS", "3"))

DISCLOSURE_DAYS = int(os.getenv("DISCLOSURE_DAYS", "7"))
PRICE_DAYS = int(os.getenv("PRICE_DAYS", "1"))
NEW_LISTING_LOOKBACK_DAYS = int(os.getenv("NEW_LISTING_LOOKBACK_DAYS", "7"))

KST = ZoneInfo("Asia/Seoul")