from __future__ import annotations
import logging
import random
from typing import Dict, Optional
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from nobroker_watchdog.utils import jitter_delay, random_user_agent

log = logging.getLogger(__name__)

class HttpError(Exception):
    pass

class Fetcher:
    def __init__(self, timeout: int, min_delay: float, max_delay: float, max_retries: int):
        self.timeout = timeout
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.session = requests.Session()

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type(HttpError),
    )
    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> requests.Response:
        hdrs = {
            "User-Agent": random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
            "Cache-Control": "no-cache",
        }
        if headers:
            hdrs.update(headers)

        jitter_delay(self.min_delay, self.max_delay)

        resp = self.session.get(url, headers=hdrs, timeout=self.timeout)
        if resp.status_code in (403, 429, 500, 502, 503, 504):
            log.warning("http_error", extra={"status": resp.status_code, "url": url})
            raise HttpError(f"HTTP {resp.status_code}")
        resp.raise_for_status()
        return resp
