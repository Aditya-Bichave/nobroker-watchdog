from __future__ import annotations

import datetime as dt
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# ---------- utilities ----------

_iso_like = re.compile(r"^\d{4}-\d{2}-\d{2}")
_digits = re.compile(r"\d+")


def to_iso(val: Any) -> Optional[str]:
    """
    Accepts:
      - ISO-like strings
      - epoch millis / seconds (int/str)
      - relative like 'posted 3 hours ago' (best-effort -> now - delta)
    Returns UTC ISO string with 'Z' or None.
    """
    try:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            # heuristics: treat > 10^12 as ms, > 10^10 as ms (android-ish), else seconds
            n = int(val)
            if n > 10_000_000_000:  # ms
                dt_ = dt.datetime.utcfromtimestamp(n / 1000.0)
            else:
                dt_ = dt.datetime.utcfromtimestamp(n)
            return dt_.isoformat() + "Z"
        s = str(val).strip()
        if not s:
            return None

        if _iso_like.match(s):
            # already ISO-ish
            try:
                # handle both with/without Z
                if s.endswith("Z"):
                    dt_ = dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc).replace(tzinfo=None)
                else:
                    dt_ = dt.datetime.fromisoformat(s)
                return dt_.isoformat() + "Z"
            except Exception:
                pass

        # relative phrases
        low = s.lower()
        now = dt.datetime.utcnow()
        if "hour" in low:
            m = _digits.search(low)
            hrs = int(m.group(0)) if m else 1
            return (now - dt.timedelta(hours=hrs)).isoformat() + "Z"
        if "minute" in low:
            m = _digits.search(low)
            mins = int(m.group(0)) if m else 1
            return (now - dt.timedelta(minutes=mins)).isoformat() + "Z"
        if "day" in low:
            m = _digits.search(low)
            days = int(m.group(0)) if m else 1
            return (now - dt.timedelta(days=days)).isoformat() + "Z"
        if "today" in low:
            return now.isoformat() + "Z"
        if "yesterday" in low:
            return (now - dt.timedelta(days=1)).isoformat() + "Z"

        # last fallback: try parsing as int
        if s.isdigit():
            return to_iso(int(s))
    except Exception:
        return None
    return None


def _int_or_none(x: Any) -> Optional[int]:
    if x in (None, ""):
        return None
    try:
        return int(x)
    except Exception:
        try:
            # extract first group of digits
            m = _digits.search(str(x))
            return int(m.group(0)) if m else None
        except Exception:
            return None


# ---------- HTML list page parsing (best-effort; returns [] on skeleton pages) ----------

_script_json_re = re.compile(
    r"window\.nb\s*=\s*window\.nb\s*\|\|\s*{}\s*;\s*nb\.pageName\s*=\s*\"listPage\";.*?nb\.appState\s*=\s*(\{.*?\})\s*;",
    re.DOTALL,
)

def parse_list_page_html(html: str) -> List[Dict[str, Any]]:
    """
    Try to extract listing cards from SSR JSON embedded in the HTML.
    Many list pages render a skeleton and fetch via XHR; in that case, we return [].
    """
    try:
        m = _script_json_re.search(html)
        if not m:
            return []
        raw = m.group(1)
        payload = json.loads(raw)
        # paths that sometimes contain results:
        candidates = [
            ("listPage", "listPageProperties"),
            ("resultScreenReducer", "propertyList"),
            ("resultScreenReducer", "propertySearchData"),
        ]
        props = []
        for a, b in candidates:
            node = (payload.get(a) or {}).get(b)
            if isinstance(node, list) and node:
                props = node
                break
        if not props:
            return []

        items: List[Dict[str, Any]] = []
        for p in props:
            listing_id = str(p.get("propertyId") or p.get("id") or "")
            if not listing_id:
                continue
            title = p.get("title") or p.get("society") or p.get("buildingName") or "Rental home"
            url_path = p.get("seoUrl") or p.get("url") or f"/property/{listing_id}"
            url = url_path if str(url_path).startswith("http") else f"https://www.nobroker.in{url_path}"
            posted_at = to_iso(p.get("lastUpdateDate") or p.get("creationDate"))
            rent = _int_or_none(p.get("rent") or p.get("rentMonthly"))
            deposit = _int_or_none(p.get("deposit") or p.get("securityDeposit"))
            bhk = _int_or_none(p.get("bhk") or p.get("bedrooms"))

            furnishing = p.get("furnishing") or p.get("furnishingDesc")
            if isinstance(furnishing, str):
                furnishing = furnishing.replace("_", " ").title()

            prop_type = p.get("propertyType") or p.get("type")
            if isinstance(prop_type, str):
                prop_type = prop_type.replace("_", " ").title()

            area_disp = p.get("locality") or p.get("location") or p.get("microMarket") or ""
            city = p.get("city") or p.get("cityName") or ""
            lat = p.get("latitude") or p.get("lat")
            lon = p.get("longitude") or p.get("lon")

            carpet = _int_or_none(p.get("carpetArea") or p.get("carpetSqft") or p.get("builtupArea"))
            floor_info = p.get("floor") or p.get("floorInfo")
            amenities = p.get("amenities") or []
            if isinstance(amenities, dict):
                amenities = [k for k, v in amenities.items() if v]
            pets = p.get("petsAllowed")
            img_count = _int_or_none(p.get("photoCount")) or len(p.get("photos") or [])
            desc = p.get("description") or p.get("propertyDescription")

            items.append({
                "listing_id": listing_id,
                "scraped_at": dt.datetime.utcnow().isoformat() + "Z",
                "title": title,
                "url": url,
                "posted_at": posted_at,
                "area_display": area_disp or "",
                "city": city or "",
                "latitude": float(lat) if lat not in (None, "") else None,
                "longitude": float(lon) if lon not in (None, "") else None,
                "price_monthly": rent or 0,
                "deposit": deposit,
                "bhk": bhk,
                "furnishing": furnishing if isinstance(furnishing, str) else None,
                "property_type": prop_type if isinstance(prop_type, str) else None,
                "carpet_sqft": carpet,
                "floor_info": str(floor_info) if floor_info not in (None, "") else None,
                "amenities": amenities if isinstance(amenities, list) else [],
                "pets_allowed": bool(pets) if pets is not None else None,
                "images_count": img_count if isinstance(img_count, int) else None,
                "description": desc,
                "match_score": 0,
                "hard_filters_passed": False,
                "soft_matches": {
                    "amenities_matched": [],
                    "proximity_km": None,
                    "carpet_ok": None,
                    "move_in_ok": None,
                },
            })
        return items
    except Exception:
        return []


# ---------- Public API JSON parsing (reliable fallback) ----------

def parse_nobroker_api_json(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse NoBroker public API v3 JSON:
    Typical: {"status":200, "data":{"totalCount":...,"nbRankedResults":[{...}, ...]}}
    """
    try:
        data = payload.get("data") or {}
        results = data.get("nbRankedResults") or data.get("data") or []
        if not isinstance(results, list):
            return []

        items: List[Dict[str, Any]] = []
        for obj in results:
            p = obj.get("property") or obj

            listing_id = str(p.get("propertyId") or p.get("id") or "")
            if not listing_id:
                continue

            title = p.get("title") or p.get("society") or p.get("buildingName") or "Rental home"
            url_path = p.get("seoUrl") or p.get("url") or f"/property/{listing_id}"
            url = url_path if str(url_path).startswith("http") else f"https://www.nobroker.in{url_path}"

            posted_at = to_iso(p.get("lastUpdateDate") or p.get("creationDate"))

            rent = _int_or_none(p.get("rent") or p.get("rentMonthly") or p.get("rentMonthlyPrice"))
            deposit = _int_or_none(p.get("deposit") or p.get("securityDeposit"))
            bhk = _int_or_none(p.get("bhk") or p.get("bedrooms"))

            furnishing = p.get("furnishing") or p.get("furnishingDesc")
            if isinstance(furnishing, str):
                furnishing = furnishing.replace("_", " ").title()

            prop_type = p.get("propertyType") or p.get("type")
            if isinstance(prop_type, str):
                prop_type = prop_type.replace("_", " ").title()

            area_disp = p.get("locality") or p.get("location") or p.get("microMarket") or ""
            city = p.get("city") or p.get("cityName") or ""
            lat = p.get("latitude") or p.get("lat")
            lon = p.get("longitude") or p.get("lon")

            carpet = _int_or_none(p.get("carpetArea") or p.get("carpetSqft") or p.get("builtupArea"))
            floor_info = p.get("floor") or p.get("floorInfo")
            amenities = p.get("amenities") or p.get("amenitiesMap") or []
            if isinstance(amenities, dict):
                amenities = [k for k, v in amenities.items() if v]
            pets = p.get("petsAllowed")
            img_count = _int_or_none(p.get("photoCount")) or len(p.get("photos") or [])
            desc = p.get("description") or p.get("propertyDescription")
            society = p.get("society") or p.get("projectName")
            if society and society not in title and title != "Rental home":
                title = f"{title} • {society}"

            items.append({
                "listing_id": listing_id,
                "scraped_at": dt.datetime.utcnow().isoformat() + "Z",
                "title": title,
                "url": url,
                "posted_at": posted_at,
                "area_display": area_disp or "",
                "city": city or "",
                "latitude": float(lat) if lat not in (None, "") else None,
                "longitude": float(lon) if lon not in (None, "") else None,
                "price_monthly": rent or 0,
                "deposit": deposit,
                "bhk": bhk,
                "furnishing": furnishing if isinstance(furnishing, str) else None,
                "property_type": prop_type if isinstance(prop_type, str) else None,
                "carpet_sqft": carpet,
                "floor_info": str(floor_info) if floor_info not in (None, "") else None,
                "amenities": amenities if isinstance(amenities, list) else [],
                "pets_allowed": bool(pets) if pets is not None else None,
                "images_count": img_count if isinstance(img_count, int) else None,
                "description": desc,
                "match_score": 0,
                "hard_filters_passed": False,
                "soft_matches": {
                    "amenities_matched": [],
                    "proximity_km": None,
                    "carpet_ok": None,
                    "move_in_ok": None,
                },
            })
        return items
    except Exception:
        return []


def parse_search_page(html: str, now: dt.datetime) -> List[Dict[str, Any]]:
    """Parse a NoBroker search results page.

    The function first attempts to extract structured JSON listings via
    :func:`parse_list_page_html`.  When no embedded data is found (common for
    skeleton pages or minimal fallbacks), it scans the HTML for plain anchor
    tags pointing to ``/property`` URLs and constructs minimal listing objects
    with sane defaults.

    Parameters
    ----------
    html:
        Raw HTML string of the search results page.
    now:
        Timestamp used for the ``scraped_at`` field in returned items.

    Returns
    -------
    List[Dict[str, Any]]
        Normalised listing dictionaries.
    """

    iso_now = now.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")

    # First try the structured SSR JSON parser
    items = parse_list_page_html(html)
    if items:
        for item in items:
            item["scraped_at"] = iso_now
        return items

    # No structured listings found: dump HTML for debugging before fallback
    try:
        debug_dir = Path(".debug")
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / "last_empty.html").write_text(html, encoding="utf-8")
    except Exception:  # pragma: no cover - best effort
        log.warning("failed to write .debug/last_empty.html", exc_info=True)

    # Fallback: parse simple anchors
    soup = BeautifulSoup(html, "html.parser")
    out: List[Dict[str, Any]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/property" not in href:
            continue
        url = href if href.startswith("http") else f"https://www.nobroker.in{href}"
        listing_id = url.rstrip("/").split("/")[-1]
        title = a.get_text(strip=True) or "Rental home"

        out.append({
            "listing_id": listing_id,
            "scraped_at": iso_now,
            "title": title,
            "url": url,
            "posted_at": None,
            "area_display": "",
            "city": "",
            "latitude": None,
            "longitude": None,
            "price_monthly": 0,
            "deposit": None,
            "bhk": None,
            "furnishing": None,
            "property_type": None,
            "carpet_sqft": None,
            "floor_info": None,
            "amenities": [],
            "pets_allowed": None,
            "images_count": None,
            "description": None,
            "match_score": 0,
            "hard_filters_passed": False,
            "soft_matches": {
                "amenities_matched": [],
                "proximity_km": None,
                "carpet_ok": None,
                "move_in_ok": None,
            },
        })

    return out


def normalize_raw_listing(raw: Dict[str, Any], now: dt.datetime) -> Dict[str, Any]:
    """Ensure a listing dictionary has the expected fields and defaults.

    This is primarily used in tests and when minimal HTML parsing is performed.
    It normalises URLs, derives the ``listing_id`` if missing and fills all
    expected keys with safe default values.
    """

    iso_now = now.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")

    url = raw.get("url") or raw.get("href")
    if url and not url.startswith("http"):
        url = f"https://www.nobroker.in{url}"

    listing_id = raw.get("listing_id")
    if not listing_id and url:
        listing_id = url.rstrip("/").split("/")[-1]

    item = {
        "listing_id": listing_id or "",
        "scraped_at": raw.get("scraped_at", iso_now),
        "title": raw.get("title") or "Rental home",
        "url": url,
        "posted_at": raw.get("posted_at"),
        "area_display": raw.get("area_display") or "",
        "city": raw.get("city") or "",
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
        "price_monthly": raw.get("price_monthly") or 0,
        "deposit": raw.get("deposit"),
        "bhk": raw.get("bhk"),
        "furnishing": raw.get("furnishing"),
        "property_type": raw.get("property_type"),
        "carpet_sqft": raw.get("carpet_sqft"),
        "floor_info": raw.get("floor_info"),
        "amenities": raw.get("amenities") if isinstance(raw.get("amenities"), list) else [],
        "pets_allowed": raw.get("pets_allowed"),
        "images_count": raw.get("images_count"),
        "description": raw.get("description"),
        "match_score": raw.get("match_score", 0),
        "hard_filters_passed": raw.get("hard_filters_passed", False),
        "soft_matches": raw.get("soft_matches") or {
            "amenities_matched": [],
            "proximity_km": None,
            "carpet_ok": None,
            "move_in_ok": None,
        },
    }

    return item
