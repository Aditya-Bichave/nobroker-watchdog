from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, Optional

import requests

log = logging.getLogger(__name__)

DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "close",
}


def fetch_url(
        url: str,
        timeout: float = 20.0,
        headers: Optional[Dict[str, str]] = None,
        min_delay: float = 1.2,
        max_delay: float = 2.4,
        max_retries: int = 3,
) -> Optional[requests.Response]:
    """
    Polite GET with random delay + exponential backoff retry.
    Returns Response or None.
    """
    hdrs = dict(DEFAULT_HEADERS)
    if headers:
        hdrs.update(headers)
    delay = random.uniform(min_delay, max_delay)

    with requests.Session() as session:
        for attempt in range(1, max_retries + 1):
            try:
                time.sleep(delay)
                t0 = time.time()
                resp = session.get(url, headers=hdrs, timeout=timeout)
                dt_ms = int((time.time() - t0) * 1000)
                log.debug("http_get_done", extra={"url": url, "status": resp.status_code, "ms": dt_ms})

                if resp.status_code in (200, 404):
                    return resp

                # 429/5xx → backoff
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise RuntimeError(f"transient_status_{resp.status_code}")

                # Other statuses: treat as terminal
                log.debug("http_unexpected_status", extra={"url": url, "status": resp.status_code})
                return None
            except Exception as e:
                if attempt >= max_retries:
                    log.debug("http_get_failed", extra={"url": url, "attempt": attempt, "err": str(e)})
                    return None
                # backoff with some jitter
                delay = min(max_delay, delay * (1.5 + random.random() * 0.5))

    return None


def fetch_json(
        url: str,
        timeout: float = 20.0,
        headers: Optional[Dict[str, str]] = None,
        min_delay: float = 1.2,
        max_delay: float = 2.4,
        max_retries: int = 3,
) -> Optional[Dict[str, Any]]:
    """
    JSON GET using the same politeness/backoff, returns dict or None.
    """
    resp = fetch_url(
        url,
        timeout=timeout,
        headers=headers,
        min_delay=min_delay,
        max_delay=max_delay,
        max_retries=max_retries,
    )
    if resp is None:
        return None
    try:
        # Prefer header; fallback on lenient parse for mislabelled responses
        if "application/json" in (resp.headers.get("Content-Type") or ""):
            return resp.json()
        text = resp.text.strip()
        if text.startswith("{") and text.endswith("}"):
            return resp.json()
    except Exception:
        log.debug("json_decode_failed", extra={"url": url})
    return None
