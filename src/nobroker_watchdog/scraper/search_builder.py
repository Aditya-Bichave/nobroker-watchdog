from __future__ import annotations
import logging
from urllib.parse import quote_plus
from typing import List

log = logging.getLogger(__name__)

def area_to_slug(area: str) -> str:
    # Very light slug for path fallback
    return area.lower().replace(",", "").replace(" ", "-")

def build_search_urls(city: str, areas: List[str]) -> List[str]:
    """
    Build public, *human* search URLs that are typically sorted by newest.
    We deliberately use public pages and parse their embedded JSON.
    These URLs are intentionally conservative to respect ToS and avoid any private API.

    If this ever changes, the parser is resilient and you can override URLs in config later.
    """
    base_city = city.lower().replace(" ", "-")
    urls = []
    for a in areas:
        # A few robust patterns NoBroker uses in public-facing pages; we try multiple
        # 1) locality (area) page
        urls.append(f"https://www.nobroker.in/property/rent/{base_city}/{area_to_slug(a)}?orderBy=lastUpdatedDate%20desc")
        # 2) generic rent-in-city search (fallback; will still contain newest)
        urls.append(f"https://www.nobroker.in/property/rent/{base_city}?searchParam={quote_plus(a)}&orderBy=lastUpdatedDate%20desc")
    # De-duplicate while preserving order
    seen = set()
    uniq = []
    for u in urls:
        if u not in seen:
            uniq.append(u)
            seen.add(u)
    log.info("search_urls_built", extra={"count": len(uniq)})
    return uniq
