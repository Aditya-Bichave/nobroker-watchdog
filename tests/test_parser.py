from datetime import datetime, timezone
from pathlib import Path

from nobroker_watchdog.scraper.parser import (
    normalize_raw_listing,
    parse_nobroker_api_json,
    parse_search_page,
)


def test_parse_search_page_fixture():
    html = Path(__file__).with_suffix("").parent / "fixtures" / "search_page_sample.html"
    s = html.read_text(encoding="utf-8")
    raw = parse_search_page(s, datetime.now(tz=timezone.utc))
    assert len(raw) >= 1
    item = normalize_raw_listing(raw[0], datetime.now(tz=timezone.utc))
    assert "listing_id" in item
    assert "url" in item

def test_soft_matches_have_floor_and_pets_keys():
    payload = {
        "data": {
            "nbRankedResults": [
                {
                    "property": {
                        "propertyId": "1",
                        "title": "Home",
                        "rent": 10000,
                    }
                }
            ]
        }
    }
    items = parse_nobroker_api_json(payload)
    assert items and "soft_matches" in items[0]
    soft = items[0]["soft_matches"]
    assert soft["floor_ok"] is None
    assert soft["pets_ok"] is None
