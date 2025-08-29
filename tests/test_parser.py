from pathlib import Path

from nobroker_watchdog.scraper.parser import (
    parse_list_page_html,
    parse_nobroker_api_json,
)


def test_parse_list_page_fixture():
    html = Path(__file__).with_suffix("").parent / "fixtures" / "search_page_sample.html"
    s = html.read_text(encoding="utf-8")
    items = parse_list_page_html(s)
    assert items, "no items parsed"
    first = items[0]
    assert "listing_id" in first
    assert "url" in first


def test_parse_nobroker_api_json_array():
    payload = {
        "data": {
            "nbRankedResults": [
                {
                    "property": {
                        "propertyId": 1,
                        "seoUrl": "/property/1",
                    }
                }
            ]
        }
    }
    items = parse_nobroker_api_json(payload)
    assert items, "no items parsed"
    assert items[0]["listing_id"] == "1"
    assert items[0]["url"].endswith("/property/1")

