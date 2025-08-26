from datetime import datetime, timezone
from pathlib import Path
from nobroker_watchdog.scraper.parser import parse_search_page, normalize_raw_listing

def test_parse_search_page_fixture():
    html = Path(__file__).with_suffix("").parent / "fixtures" / "search_page_sample.html"
    s = html.read_text(encoding="utf-8")
    raw = parse_search_page(s, datetime.now(tz=timezone.utc))
    assert len(raw) >= 1
    item = normalize_raw_listing(raw[0], datetime.now(tz=timezone.utc))
    assert "listing_id" in item
    assert "url" in item
