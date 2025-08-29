from nobroker_watchdog.scraper import fetcher

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
    
def _make_response(body: str, content_type: str = "text/plain") -> Response:
    resp = Response()
    resp.status_code = 200
    resp._content = body.encode("utf-8")
    resp.headers["Content-Type"] = content_type
    return resp


def test_fetch_json_array(monkeypatch):
    resp = _make_response('[{"value": 1}]')

    monkeypatch.setattr(fetcher, "fetch_url", lambda *args, **kwargs: resp)

    data = fetcher.fetch_json("http://example.com")
    assert isinstance(data, list)
    assert data[0]["value"] == 1


def test_fetch_json_invalid(monkeypatch):
    resp = _make_response("not json")

    monkeypatch.setattr(fetcher, "fetch_url", lambda *args, **kwargs: resp)

    data = fetcher.fetch_json("http://example.com")
    assert data is None

