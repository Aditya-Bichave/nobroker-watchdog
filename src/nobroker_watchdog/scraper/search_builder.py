from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

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
) -> List[SearchTarget]:
    """
    For each area, build three ordered targets:
      1) HTML locality path (SSR if available)
      2) HTML text searchParam fallback
      3) Public API JSON (only if coordinates were provided for the area)

    We dedupe identical URLs and keep order stable.
    """
    targets: List[SearchTarget] = []
    city_slug = _slugify(city)

    for area in areas:
        area_clean = (area or "").strip()
        if not area_clean:
            continue

        area_slug = _slugify(area_clean)

        # Ensure we don't accidentally duplicate '-<city>' when area already contains it
        if area_slug.endswith(f"-{city_slug}"):
            path_slug = area_slug
        else:
            path_slug = f"{area_slug}-{city_slug}"

        # 1) HTML locality path (prefer this; it's the cleanest URL)
        html_path = (
            f"https://www.nobroker.in/property/rent/{city_slug}/{path_slug}"
            f"?orderBy={order_by.replace(' ', '%20')}"
        )
        targets.append(SearchTarget(kind="html", url=html_path, area_name=area_clean))

        # 2) HTML text searchParam fallback
        html_text = (
            f"https://www.nobroker.in/property/rent/{city_slug}"
            f"?searchParam={area_clean.replace(' ', '+')}"
            f"&sharedAccomodation=0&orderBy={order_by.replace(' ', '%20')}"
        )
        targets.append(SearchTarget(kind="html", url=html_text, area_name=area_clean))

        # 3) API JSON if we have coordinates (more precise & often populated even when SSR is skeleton)
        if area_coords and area_clean in area_coords:
            lat, lon = area_coords[area_clean]
            b64 = _encode_search_param(area_clean, lat, lon)
            api_url = (
                "https://www.nobroker.in/api/v3/multi/property/filter"
                f"?searchParam={b64}&sharedAccomodation=0"
                f"&orderBy={order_by.replace(' ', '%20')}"
                "&page=0&limit=30"
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
