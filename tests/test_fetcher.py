from requests.models import Response

from nobroker_watchdog.scraper import fetcher


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
