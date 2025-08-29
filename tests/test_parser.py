
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

    def test_html_and_api_normalization(monkeypatch):
    fixed = datetime(2024, 1, 1)

    class FixedDatetime(datetime):
        @classmethod
        def utcnow(cls):  # pragma: no cover - simple monkeypatch helper
            return fixed

    monkeypatch.setattr(parser.dt, "datetime", FixedDatetime)

    prop = {
        "propertyId": 123,
        "title": "Nice Flat",
        "society": "Happy Homes",
        "seoUrl": "/some-url",
        "lastUpdateDate": "2024-01-01",
        "rent": 10000,
        "deposit": 20000,
        "bhk": 2,
        "furnishing": "semi_furnished",
        "propertyType": "apartment",
        "locality": "Area",
        "city": "Bangalore",
        "latitude": "12.34",
        "longitude": "56.78",
        "carpetArea": 750,
        "floor": "3 of 5",
        "amenities": {"Gym": True, "Pool": False},
        "petsAllowed": True,
        "photoCount": 5,
        "description": "Nice place",
    }

    html_payload = {"listPage": {"listPageProperties": [prop]}}
    html = (
        "window.nb=window.nb||{};nb.pageName=\"listPage\";nb.appState="
        f"{json.dumps(html_payload)};"
    )

    api_payload = {"data": {"nbRankedResults": [{"property": prop}]}}

    html_items = parser.parse_list_page_html(html)
    api_items = parser.parse_nobroker_api_json(api_payload)
    assert html_items == api_items


def test_invalid_lat_lon(monkeypatch):
    fixed = datetime(2024, 1, 1)

    class FixedDatetime(datetime):
        @classmethod
        def utcnow(cls):  # pragma: no cover - simple monkeypatch helper
            return fixed

    monkeypatch.setattr(parser.dt, "datetime", FixedDatetime)

    prop = {
        "propertyId": 321,
        "title": "Another Flat",
        "seoUrl": "/other-url",
        "latitude": "not-a-num",
        "longitude": "also-bad",
    }

    html_payload = {"listPage": {"listPageProperties": [prop]}}
    html = (
        "window.nb=window.nb||{};nb.pageName=\"listPage\";nb.appState="
        f"{json.dumps(html_payload)};"
    )
    api_payload = {"data": {"nbRankedResults": [{"property": prop}]}}

    html_items = parser.parse_list_page_html(html)
    api_items = parser.parse_nobroker_api_json(api_payload)
    assert html_items == api_items
    assert html_items[0]["latitude"] is None
    assert html_items[0]["longitude"] is None