from nobroker_watchdog.scraper.parser import parse_nobroker_api_json


def test_parse_nobroker_api_json_minimal():
    payload = {"data": {"data": [{"id": 123, "seoUrl": "/property/123"}]}}
    items = parse_nobroker_api_json(payload)
    assert items, "Expected at least one listing"
    item = items[0]
    assert item["listing_id"] == "123"
    assert item["url"].endswith("/property/123")
    assert item["scraped_at"].endswith("Z")
