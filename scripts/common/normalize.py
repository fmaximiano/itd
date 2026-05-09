from __future__ import annotations

import math
import unicodedata
from typing import Any, Optional

import pandas as pd


def normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None

    if pd.isna(value):
        return None

    if isinstance(value, float) and math.isnan(value):
        return None

    text = str(value).strip()

    if text in ("", "-"):
        return None

    text = " ".join(text.split())
    text = unicodedata.normalize("NFC", text)

    return text if text else None