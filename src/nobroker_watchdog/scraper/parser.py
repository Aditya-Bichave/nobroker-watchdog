from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from bs4 import BeautifulSoup

from nobroker_watchdog.utils import parse_indic_money, parse_relative_time

log = logging.getLogger(__name__)

@dataclass
class RawListing:
    listing_id: str
    url: str
    title: Optional[str]
    area_display: Optional[str]
    city: Optional[str]
    posted_text: Optional[str]
    monthly_rent_text: Optional[str]
    deposit_text: Optional[str]
    bhk_text: Optional[str]
    furnishing_text: Optional[str]
    property_type_text: Optional[str]
    floor_info_text: Optional[str]
    carpet_text: Optional[str]
    amenities: List[str]
    images_count: Optional[int]
    description: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    society: Optional[str]

def _walk_json(obj: Any) -> Iterable[Dict[str, Any]]:
    """Yield all dicts in JSON tree."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_json(v)
    elif isinstance(obj, list):
        for i in obj:
            yield from _walk_json(i)

def _extract_next_data(soup: BeautifulSoup) -> Optional[dict]:
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return None
    try:
        return json.loads(script.string)
    except Exception:
        return None

def _guess_listings_from_json(next_data: dict) -> List[RawListing]:
    listings: List[RawListing] = []
    for node in _walk_json(next_data):
        # Heuristics: typical listing dicts have id/propertyId + rent + location
        keys = node.keys()
        cond_id = any(k in keys for k in ("id", "propertyId", "property_id"))
        cond_rent = any(k in keys for k in ("rent", "rentPrice", "monthlyRent"))
        cond_loc = any(k in keys for k in ("locality", "location", "city"))
        if not (cond_id and cond_rent and cond_loc):
            continue

        listing_id = str(node.get("id") or node.get("propertyId") or node.get("property_id"))
        url = node.get("shortUrl") or node.get("seoUrl") or node.get("url") or ""
        if url and url.startswith("/"):
            url = "https://www.nobroker.in" + url

        title = node.get("title") or node.get("seoTitle") or node.get("description") or ""
        area_display = node.get("locality") or node.get("location")
        city = node.get("city")
        posted_text = node.get("creationDate") or node.get("postedOn") or node.get("postedAt") or node.get("posted")
        monthly_rent_text = str(node.get("rent") or node.get("monthlyRent") or "")
        deposit_text = str(node.get("deposit") or node.get("securityDeposit") or "")
        bhk_text = str(node.get("bedrooms") or node.get("bhk") or node.get("propertyConfiguration") or "")
        furnishing_text = node.get("furnishing") or node.get("furnishingType")
        property_type_text = node.get("propertyType") or node.get("type")
        floor_info_text = node.get("floor") or node.get("floorDisplayLabel")
        carpet_text = str(node.get("carpetArea") or node.get("area") or "")
        amenities = [a for a in (node.get("amenities") or []) if isinstance(a, str)]
        images_count = None
        photos = node.get("photos") or node.get("images")
        if isinstance(photos, list):
            images_count = len(photos)
        description = node.get("description")
        lat = node.get("latitude") or node.get("lat")
        lng = node.get("longitude") or node.get("lng")
        society = node.get("society") or node.get("projectName")

        if listing_id:
            listings.append(
                RawListing(
                    listing_id=listing_id,
                    url=url,
                    title=title,
                    area_display=area_display,
                    city=city,
                    posted_text=str(posted_text) if posted_text else None,
                    monthly_rent_text=monthly_rent_text,
                    deposit_text=deposit_text,
                    bhk_text=bhk_text,
                    furnishing_text=str(furnishing_text) if furnishing_text else None,
                    property_type_text=str(property_type_text) if property_type_text else None,
                    floor_info_text=str(floor_info_text) if floor_info_text else None,
                    carpet_text=carpet_text,
                    amenities=amenities,
                    images_count=images_count,
                    description=description,
                    latitude=float(lat) if isinstance(lat, (int, float, str)) and str(lat) else None,
                    longitude=float(lng) if isinstance(lng, (int, float, str)) and str(lng) else None,
                    society=society,
                )
            )
    return listings

def _fallback_parse_cards(soup: BeautifulSoup) -> List[RawListing]:
    # Conservative fallback if JSON not available; try to parse card elements
    listings: List[RawListing] = []
    cards = soup.select('a[href*="/property/"]')  # broad
    for a in cards[:60]:  # limit
        url = a.get("href")
        if url and url.startswith("/"):
            url = "https://www.nobroker.in" + url
        title = a.get_text(strip=True) or None
        # not all fields are present in fallback; that's ok
        listings.append(
            RawListing(
                listing_id=url or title or "",
                url=url or "",
                title=title,
                area_display=None,
                city=None,
                posted_text=None,
                monthly_rent_text=None,
                deposit_text=None,
                bhk_text=None,
                furnishing_text=None,
                property_type_text=None,
                floor_info_text=None,
                carpet_text=None,
                amenities=[],
                images_count=None,
                description=None,
                latitude=None,
                longitude=None,
                society=None,
            )
        )
    return listings

def parse_search_page(html: str, now: datetime) -> List[RawListing]:
    soup = BeautifulSoup(html, "html.parser")

    # Prefer Next.js data
    next_data = _extract_next_data(soup)
    if next_data:
        lst = _guess_listings_from_json(next_data)
        if lst:
            return lst

    # Fallback
    return _fallback_parse_cards(soup)

def normalize_raw_listing(raw: RawListing, now: datetime) -> Dict[str, Any]:
    # Convert RawListing to strict schema with best-effort inference
    posted_at = None
    if raw.posted_text:
        posted_at = parse_relative_time(raw.posted_text, now)

    price = parse_indic_money(raw.monthly_rent_text) or 0
    deposit = parse_indic_money(raw.deposit_text) if raw.deposit_text else None

    # infer BHK if needed
    bhk = None
    if raw.bhk_text:
        m = re.search(r"(\d+)\s*BHK", raw.bhk_text, re.I)
        if m:
            bhk = int(m.group(1))
        else:
            try:
                bhk = int(raw.bhk_text)
            except Exception:
                pass
    if bhk is None and raw.title:
        m2 = re.search(r"(\d+)\s*BHK", raw.title, re.I)
        if m2:
            bhk = int(m2.group(1))

    # carpet area
    carpet_sqft = None
    sources = [raw.carpet_text or "", raw.description or "", raw.title or ""]
    for src in sources:
        m = re.search(r"(\d{3,5})\s*(sq\.?\s*ft|sqft|sft|ft2)", src, re.I)
        if m:
            carpet_sqft = int(m.group(1))
            break

    data: Dict[str, Any] = {
        "listing_id": raw.listing_id,
        "scraped_at": now.isoformat(),
        "title": raw.title or "",
        "url": raw.url,
        "posted_at": posted_at.isoformat() if posted_at else None,
        "area_display": raw.area_display or "",
        "city": raw.city or "",
        "latitude": raw.latitude,
        "longitude": raw.longitude,
        "price_monthly": price,
        "deposit": deposit,
        "bhk": bhk,
        "furnishing": (raw.furnishing_text or "").strip() or None,
        "property_type": (raw.property_type_text or "").strip() or None,
        "carpet_sqft": carpet_sqft,
        "floor_info": (raw.floor_info_text or "").strip() or None,
        "amenities": [a.strip().lower() for a in raw.amenities if isinstance(a, str)],
        "pets_allowed": None,  # often not explicit; matcher can infer from description keywords
        "images_count": raw.images_count,
        "description": raw.description or None,
        # filled by matcher:
        "match_score": 0,
        "hard_filters_passed": False,
        "soft_matches": {
            "amenities_matched": [],
            "proximity_km": None,
            "carpet_ok": None,
            "move_in_ok": None,
        },
    }
    return data
