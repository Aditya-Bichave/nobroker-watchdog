from types import SimpleNamespace

from nobroker_watchdog.main import run_once
from nobroker_watchdog.scraper.search_builder import SearchTarget


def test_run_once_skips_duplicate_listing_ids(monkeypatch):
    cfg = SimpleNamespace(
        city="City",
        areas=["A", "B"],
        area_coords=None,
        http_timeout_seconds=1,
        http_min_delay_seconds=0,
        http_max_delay_seconds=0,
        max_retries=0,
    )

    targets = [
        SearchTarget(kind="api", url="url1", area_name="Area1"),
        SearchTarget(kind="api", url="url2", area_name="Area2"),
    ]
    monkeypatch.setattr("nobroker_watchdog.main.build_search_targets", lambda **kwargs: targets)
    monkeypatch.setattr("nobroker_watchdog.main.fetch_json", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(
        "nobroker_watchdog.main.parse_nobroker_api_json", lambda payload: [{"listing_id": "1"}]
    )

    summary = run_once(cfg)
    assert summary["cards_seen"] == 1
