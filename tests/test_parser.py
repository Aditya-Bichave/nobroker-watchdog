from datetime import datetime, timezone
from pathlib import Path
from nobroker_watchdog.scraper.parser import parse_search_page, normalize_raw_listing

def test_parse_search_page_fixture():
    html = Path(__file__).with_suffix("").parent / "fixtures" / "search_page_sample.html"
    s = html.read_text(encoding="utf-8")
    now = datetime.now(tz=timezone.utc)
    raw = parse_search_page(s, now)
    assert len(raw) >= 1
    item = normalize_raw_listing(raw[0], now)
    assert item["listing_id"] == "test-listing-id-1234"
    assert item["url"] == (
        "https://www.nobroker.in/property/for-rent/test-listing-id-1234"
    )
    assert item["price_monthly"] == 0
    assert item["amenities"] == []
