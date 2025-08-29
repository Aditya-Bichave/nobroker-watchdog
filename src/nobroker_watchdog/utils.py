from __future__ import annotations
import hashlib
import math
import random
import re
import time
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Tuple

from dateutil import parser as dateutil_parser
import dateparser

UA_LIST = [
    # A few rotated desktop/mobile user-agents
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko)"
    " Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/118.0.0.0 Mobile Safari/537.36",
]

def random_user_agent() -> str:
    return random.choice(UA_LIST)

def jitter_delay(min_s: float, max_s: float) -> None:
    t = random.uniform(min_s, max_s)
    time.sleep(t)

def sha1_fingerprint(parts: Iterable[Any]) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update(str(p).encode("utf-8", "ignore"))
        h.update(b"\x00")
    return h.hexdigest()

def parse_indic_money(s: str | None) -> Optional[int]:
    if not s:
        return None
    s = s.replace(",", "").strip().lower()
    # Handle formats like "₹35,000", "35000", "35k", "35k/month"
    m = re.search(r"(\d+(?:\.\d+)?)(\s*[kK]|(?:\s*l|lakh))?", s)
    if not m:
        digits = re.sub(r"\D+", "", s)
        if digits:
            return int(digits)
        return None
    num = float(m.group(1))
    unit = (m.group(2) or "").strip().lower()
    if unit in {"k", "k/month", "k/mon"}:
        num *= 1000
    elif unit in {"l", "lakh"}:
        num *= 100000
    return int(num)

def parse_relative_time(text: str, now: datetime) -> Optional[datetime]:
    """
    Accepts strings like:
    - "Posted today"
    - "Posted 3 hours ago"
    - "3h ago"
    - "yesterday"
    - "2025-08-25"
    - "25 Aug 2025"
    """
    if not text:
        return None
    text = text.strip()
    # try dateparser (handles tons of human times)
    dt = dateparser.parse(text, settings={"RELATIVE_BASE": now})
    if dt:
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    # try dateutil as fallback
    try:
        dt2 = dateutil_parser.parse(text)
        return dt2.astimezone(timezone.utc)
    except Exception:
        return None

def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    R = 6371.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(h))
