from __future__ import annotations

import datetime as dt
import json
import logging
import re
from typing import Any, Dict, List, Optional

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


def _float_or_none(x: Any) -> Optional[float]:
    if x in (None, ""):
        return None
    try:
        return float(x)
    except Exception:
        try:
            m = _digits.search(str(x))
            return float(m.group(0)) if m else None
        except Exception:
            return None


def _normalize_property(p: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map a raw property dict to the normalized schema used by the scraper."""
    listing_id = str(p.get("propertyId") or p.get("id") or "")
    if not listing_id:
        return None

    title = p.get("title") or p.get("society") or p.get("buildingName") or "Rental home"
    society = p.get("society") or p.get("projectName")
    if society and society not in title and title != "Rental home":
        title = f"{title} • {society}"

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
    lat = _float_or_none(p.get("latitude") or p.get("lat"))
    lon = _float_or_none(p.get("longitude") or p.get("lon"))

    carpet = _int_or_none(p.get("carpetArea") or p.get("carpetSqft") or p.get("builtupArea"))
    floor_info = p.get("floor") or p.get("floorInfo")
    amenities = p.get("amenities") or p.get("amenitiesMap") or []
    if isinstance(amenities, dict):
        amenities = [k for k, v in amenities.items() if v]
    pets = p.get("petsAllowed")
    img_count = _int_or_none(p.get("photoCount")) or len(p.get("photos") or [])
    desc = p.get("description") or p.get("propertyDescription")

    return {
        "listing_id": listing_id,
        "scraped_at": dt.datetime.utcnow().isoformat() + "Z",
        "title": title,
        "url": url,
        "posted_at": posted_at,
        "area_display": area_disp or "",
        "city": city or "",
        "latitude": lat,
        "longitude": lon,
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
    }


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
            norm = _normalize_property(p)
            if norm:
                items.append(norm)
        return items
    except Exception:
        return []


def parse_search_page(html: str, _now: dt.datetime) -> List[Dict[str, Any]]:
    """Parse a search results HTML page.

    Attempts the full JSON-based extraction first; if that yields nothing, falls
    back to a minimal anchor-tag scan which is primarily used in tests.
    The ``_now`` parameter is accepted for API compatibility but is not used.
    """

    items = parse_list_page_html(html)
    if items:
        return items

    try:
        results: List[Dict[str, Any]] = []
        for href, _text in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.I):
            if "/property/" not in href:
                continue
            listing_id = href.rstrip("/").split("/")[-1]
            url = href if href.startswith("http") else f"https://www.nobroker.in{href}"
            results.append({"listing_id": listing_id, "url": url})
        return results
    except Exception:
        return []


def normalize_raw_listing(raw: Dict[str, Any], _now: dt.datetime) -> Dict[str, Any]:
    """Normalize a raw listing structure.

    Listings returned by :func:`parse_list_page_html` are already normalized, so
    this function simply returns the ``raw`` value unchanged.
    """

    return raw


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
            norm = _normalize_property(p)
            if norm:
                items.append(norm)
        return items
    except Exception:
        return []
