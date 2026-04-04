from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from settings import KST


class CollectorError(RuntimeError):
    pass


class KRXAPIError(CollectorError):
    pass


class DARTAPIError(CollectorError):
    pass


class DatabaseError(CollectorError):
    pass


def log(*args: Any, verbose: bool = False) -> None:
    if verbose:
        print(*args, file=sys.stderr)


def kst_now() -> datetime:
    return datetime.now(KST)


def kst_today() -> date:
    return kst_now().date()


def yyyymmdd(d: date) -> str:
    return d.strftime("%Y%m%d")


def parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw == "-":
        return None

    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass

    digits = re.sub(r"\D", "", raw)
    if len(digits) == 8:
        try:
            return datetime.strptime(digits, "%Y%m%d").date()
        except ValueError:
            return None
    return None


def previous_business_day(ref: Optional[date] = None) -> date:
    cur = ref or kst_today()
    cur -= timedelta(days=1)
    while cur.weekday() >= 5:
        cur -= timedelta(days=1)
    return cur


def business_days_back(end_date: date, days: int) -> list[date]:
    out: list[date] = []
    cur = end_date
    while len(out) < days:
        if cur.weekday() < 5:
            out.append(cur)
        cur -= timedelta(days=1)
    out.sort()
    return out


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_stock_code(value: Any) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip().upper()
    if raw.startswith("A") and len(raw) >= 7:
        raw = raw[1:]
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    if len(digits) > 6:
        digits = digits[-6:]
    return digits.zfill(6)


def normalize_holder_key(value: Any) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", normalize_text(value).lower())


def to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    raw = str(value).strip().replace(",", "")
    if not raw or raw == "-":
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def to_int(value: Any) -> Optional[int]:
    d = to_decimal(value)
    return int(d) if d is not None else None


def quant2(value: Optional[Decimal]) -> Optional[Decimal]:
    if value is None:
        return None
    return value.quantize(Decimal("0.01"))


def quant4(value: Optional[Decimal]) -> Optional[Decimal]:
    if value is None:
        return None
    return value.quantize(Decimal("0.0001"))


def safe0(value: Optional[Decimal]) -> Decimal:
    return quant4(value) or Decimal("0")


def calc_return_since_ipo(offering_price: Optional[Decimal], current_price: Optional[Decimal]) -> Optional[Decimal]:
    if offering_price is None or current_price is None or offering_price == 0:
        return None
    return quant2((current_price - offering_price) / offering_price * Decimal("100"))


def json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Cannot serialize type: {type(value)}")


def dumps_pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=json_default)


def sleep_retry(attempt: int) -> None:
    time.sleep(min(2 ** (attempt - 1), 5))