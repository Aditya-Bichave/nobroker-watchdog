from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus

log = logging.getLogger(__name__)
_slugify_re = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class SearchTarget:
    """
    Represents one fetchable target for an area.
    kind: 'html' | 'api'
    url: full URL to request
    area_name: human-readable area name
    b64: base64-encoded searchParam (used by API), if available
    """
    kind: str
    url: str
    area_name: str
    b64: Optional[str] = None


def _slugify(text: str) -> str:
    s = (text or "").strip().lower()
    s = _slugify_re.sub("-", s).strip("-")
    return s


def _encode_search_param(place_name: str, lat: Optional[float], lon: Optional[float]) -> str:
    """
    NoBroker accepts base64(JSON array) for searchParam, e.g.:
    [{"placeName":"Kadubeesanahalli, Bangalore","placeId":"","lat":"12.935400","lon":"77.697400"}]
    """
    payload = [{
        "placeName": place_name,
        "placeId": "",
        "lat": f"{lat:.6f}" if lat is not None else "",
        "lon": f"{lon:.6f}" if lon is not None else "",
    }]
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def build_search_targets(
        city: str,
        areas: List[str],
        order_by: str = "lastUpdatedDate desc",
        area_coords: Optional[Dict[str, Tuple[float, float]]] = None,
        bhk_in: Optional[List[int]] = None,
        furnishing_in: Optional[List[str]] = None,
        carpet_min_sqft: Optional[int] = None,
        floors_allowed_in: Optional[List[str]] = None,
        proximity_km: Optional[float] = None,
) -> List[SearchTarget]:
    """Build ordered search targets for each area.

    The primary HTML target uses a ``searchParam`` with coordinates when available
    which results in server-side rendered listings.  Additional query
    parameters are attached based on the provided filters.  A public API target
    is also generated when coordinates exist, acting as a reliable fallback.
    """
    targets: List[SearchTarget] = []
    city_slug = _slugify(city)

    # Pre-build query parts for optional filters
    type_part = ""
    if bhk_in:
        type_part = "&type=" + ",".join(f"BHK{b}" for b in bhk_in)

    furnish_map = {
        "Fully Furnished": "FULLY_FURNISHED",
        "Semi-Furnished": "SEMI_FURNISHED",
        "Unfurnished": "NOT_FURNISHED",
    }
    furnish_part = ""
    if furnishing_in:
        codes = [furnish_map.get(f, f.upper().replace(" ", "_")) for f in furnishing_in]
        furnish_part = "&furnishing=" + ",".join(codes)

    farea_part = f"&farea={carpet_min_sqft},10000" if carpet_min_sqft else ""
    floor_part = f"&floor={','.join(floors_allowed_in)}" if floors_allowed_in else ""
    radius_part = f"&radius={proximity_km}" if proximity_km is not None else ""

    for area in areas:
        area_clean = (area or "").strip()
        if not area_clean:
            continue

        base_name = area_clean.split(",")[0].strip()
        area_slug = _slugify(base_name)

        b64 = None
        if area_coords and area_clean in area_coords:
            lat, lon = area_coords[area_clean]
            b64 = _encode_search_param(base_name, lat, lon)

        # 1) HTML locality path with searchParam if available
        if b64:
            html_path = (
                f"https://www.nobroker.in/property/rent/{city_slug}/{area_slug}"
                f"?searchParam={b64}{radius_part}&sharedAccomodation=0"
                f"&city={city_slug}&locality={quote_plus(base_name)}"
                f"{type_part}{furnish_part}{farea_part}{floor_part}"
                f"&orderBy={order_by.replace(' ', '%20')}"
            )
            targets.append(SearchTarget(kind="html", url=html_path, area_name=area_clean, b64=b64))
        else:
            # Fallback to simple slug URL
            html_path = (
                f"https://www.nobroker.in/property/rent/{city_slug}/{area_slug}-{city_slug}"
                f"?orderBy={order_by.replace(' ', '%20')}"
            )
            targets.append(SearchTarget(kind="html", url=html_path, area_name=area_clean))

        # 2) Text search fallback
        html_text = (
            f"https://www.nobroker.in/property/rent/{city_slug}"
            f"?searchParam={quote_plus(area_clean)}&sharedAccomodation=0"
            f"&orderBy={order_by.replace(' ', '%20')}"
        )
        targets.append(SearchTarget(kind="html", url=html_text, area_name=area_clean))

        # 3) API JSON if coordinates exist
        if b64:
            api_url = (
                "https://www.nobroker.in/api/v3/multi/property/filter"
                f"?searchParam={b64}{radius_part}&sharedAccomodation=0"
                f"&orderBy={order_by.replace(' ', '%20')}"
                "&page=0&limit=30"
                f"{type_part}{furnish_part}{farea_part}{floor_part}"
            )
            targets.append(SearchTarget(kind="api", url=api_url, area_name=area_clean, b64=b64))

    # De-duplicate while preserving order
    seen: set[tuple[str, str]] = set()
    deduped: List[SearchTarget] = []
    for t in targets:
        key = (t.kind, t.url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)

    log.info("search_urls_built", extra={"count": len(deduped)})
    return deduped
