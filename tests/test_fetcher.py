from unittest.mock import Mock

import requests

from nobroker_watchdog.scraper.fetcher import fetch_url


class DummySession:
    def __init__(self):
        self.get = Mock()
        self.close = Mock()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def test_fetch_url_closes_session(monkeypatch):
    dummy = DummySession()
    dummy.get.return_value = Mock(status_code=200)
    monkeypatch.setattr(requests, "Session", lambda: dummy)

    fetch_url("http://example.com", min_delay=0, max_delay=0, max_retries=1)

    dummy.close.assert_called_once()
