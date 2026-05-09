from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

import pandas as pd

from scripts.common.normalize import normalize_text


def now_utc() -> datetime:
    return datetime.utcnow()


def parse_date_br(value: Any) -> Optional[date]:
    if value is None:
        return None

    if pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.date()

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    try:
        parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
        if pd.notna(parsed):
            return parsed.date()
    except Exception:
        pass

    text = normalize_text(value)
    if text is None:
        return None

    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    return None


def parse_int64(value: Any) -> Optional[int]:
    text = normalize_text(value)
    if text is None:
        return None

    try:
        return int(float(text))
    except Exception:
        return None


def parse_nullable_int_formula(value: Any) -> Optional[int]:
    text = normalize_text(value)
    if text is None:
        return None

    try:
        return int(float(text))
    except Exception:
        return None