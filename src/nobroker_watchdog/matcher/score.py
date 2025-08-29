from __future__ import annotations
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from nobroker_watchdog.utils import haversine_km

log = logging.getLogger(__name__)

def _contains_excluded(texts: List[str], excluded: List[str]) -> bool:
    body = " ".join(t.lower() for t in texts if t)
    return any(kw.lower() in body for kw in excluded)

def _amenities_match(amenities: List[str], required_any: List[str]) -> List[str]:
    a_set = {a.strip().lower() for a in amenities}
    matches = []
    for req in required_any:
        r = req.strip().lower()
        for a in a_set:
            if r in a or a in r:
                matches.append(req)
                break
    return sorted(set(matches))

def _floor_ok(floor_info: Optional[str], floors_allowed: List[str]) -> bool:
    if not floors_allowed or not floor_info:
        return True
    norm = floor_info.lower()
    for f in floors_allowed:
        f = f.lower()
        if f.endswith("+"):
            try:
                min_f = int(re.sub(r"\D+", "", f))
                num = int(re.sub(r"\D+", "", norm) or -999)
                if num >= min_f:
                    return True
            except Exception:
                continue
        if f in norm:
            return True
    return False

def _infer_pets(description: Optional[str]) -> Optional[bool]:
    if not description:
        return None
    s = description.lower()
    if "pets allowed" in s or "pet friendly" in s:
        return True
    if "no pets" in s or "pets not allowed" in s:
        return False
    return None

def hard_pass(
    item: Dict,
    areas: List[str],
    city: str,
    budget_min: int,
    budget_max: int,
    bhk_in: List[int],
    furnishing_in: List[str],
    property_types_in: List[str],
    max_age_hours: int,
    area_coords: Dict[str, Tuple[float, float]] | None,
    proximity_km: Optional[float],
) -> Tuple[bool, Optional[float]]:
    now = datetime.now(tz=timezone.utc)
    # area match or within radius
    area_txt = (item.get("area_display") or "").lower()
    area_ok = any(
        a and (a.lower() in area_txt or area_txt in a.lower()) for a in areas
    )
    prox_km = None

    if not area_ok and proximity_km and item.get("latitude") and item.get("longitude") and area_coords:
        # check smallest distance to any configured area center
        px, py = float(item["latitude"]), float(item["longitude"])
        distances = []
        for a, (lat, lng) in area_coords.items():
            d = haversine_km((px, py), (lat, lng))
            distances.append(d)
        if distances:
            prox_km = min(distances)
            area_ok = prox_km <= proximity_km

    # budget range
    price = int(item.get("price_monthly") or 0)
    budget_ok = budget_min <= price <= budget_max

    # BHK
    bhk = item.get("bhk")
    bhk_ok = bhk is None or bhk in set(bhk_in)  # missing bhk => allow (fallback inference)

    # furnishing
    furn = (item.get("furnishing") or "").strip()
    furnishing_ok = (not furnishing_in) or (furn in furnishing_in)

    # type
    ptype = (item.get("property_type") or "").strip()
    type_ok = (not property_types_in) or (ptype in property_types_in)

    # listing age
    age_ok = True
    if item.get("posted_at"):
        from dateutil import parser as dateutil_parser
        ts = dateutil_parser.isoparse(item["posted_at"])
        age_hours = (now - ts).total_seconds() / 3600.0
        age_ok = age_hours <= max_age_hours

    return all([area_ok, budget_ok, bhk_ok, furnishing_ok, type_ok, age_ok]), prox_km

def soft_score(
    item: Dict,
    required_amenities_any: List[str],
    carpet_min_sqft: int,
    floors_allowed_in: List[str],
    pets_allowed: Optional[bool],
    move_in_by: Optional[str],
) -> Tuple[int, Dict]:
    # weights (sum 100)
    W_AMEN = 40
    W_CARPET = 20
    W_FLOOR = 15
    W_PETS = 10
    W_MOVEIN = 15

    matches = {
        "amenities_matched": [],
        "proximity_km": item.get("soft_matches", {}).get("proximity_km"),
        "carpet_ok": None,
        "move_in_ok": None,
    }

    score = 0

    # amenities (any subset)
    am = _amenities_match(item.get("amenities") or [], required_amenities_any)
    matches["amenities_matched"] = am
    if required_amenities_any:
        score += int(W_AMEN * (len(am) / len(set(required_amenities_any))))
    else:
        score += W_AMEN  # no requirements -> full credit

    # carpet
    carpet_ok = None
    c = item.get("carpet_sqft")
    if isinstance(c, int):
        carpet_ok = c >= carpet_min_sqft if carpet_min_sqft else True
        if carpet_ok:
            score += W_CARPET
    matches["carpet_ok"] = carpet_ok

    # floor
    floor_ok = _floor_ok(item.get("floor_info"), floors_allowed_in)
    if floor_ok:
        score += W_FLOOR

    # pets
    pets_inferred = _infer_pets(item.get("description"))
    pets_ok = True
    if pets_allowed is not None:
        if pets_inferred is None:
            pets_ok = True  # unknown -> don't penalize
        else:
            pets_ok = pets_inferred == pets_allowed
    if pets_ok:
        score += W_PETS

    # move-in by (approximation: posted date suggests availability soon)
    move_in_ok = None
    if move_in_by and item.get("posted_at"):
        from dateutil import parser as dateutil_parser
        want = dateutil_parser.parse(move_in_by).date()
        posted = dateutil_parser.isoparse(item["posted_at"]).date()
        # If posted <= desired move-in-by + 45 days buffer
        from datetime import timedelta
        move_in_ok = posted <= (want + timedelta(days=45))
        if move_in_ok:
            score += W_MOVEIN
    matches["move_in_ok"] = move_in_ok

    return score, matches
