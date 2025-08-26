from datetime import datetime, timezone, timedelta
from nobroker_watchdog.matcher.score import hard_pass, soft_score

def test_soft_score_basic():
    item = {
        "amenities": ["lift", "security", "gym"],
        "carpet_sqft": 650,
        "floor_info": "2 of 5",
        "description": "Pet friendly apartment with great security and lift.",
        "posted_at": (datetime.now(tz=timezone.utc) - timedelta(hours=6)).isoformat(),
        "soft_matches": {},
    }
    score, soft = soft_score(
        item,
        required_amenities_any=["lift","parking","security","power backup","gym","pool"],
        carpet_min_sqft=550,
        floors_allowed_in=["Ground","1","2","3","4+"],
        pets_allowed=True,
        move_in_by="2025-09-30",
    )
    assert score >= 70
    assert soft["carpet_ok"] is True
    assert "lift" in soft["amenities_matched"]

def test_hard_pass_budget_area():
    item = {
        "area_display": "Kadubeesanahalli",
        "price_monthly": 30000,
        "bhk": 2,
        "furnishing": "Semi-Furnished",
        "property_type": "Apartment",
        "posted_at": (datetime.now(tz=timezone.utc) - timedelta(hours=3)).isoformat(),
        "latitude": None,
        "longitude": None,
    }
    ok, prox = hard_pass(
        item,
        areas=["Kadubeesanahalli, Bangalore"],
        city="Bangalore",
        budget_min=20000,
        budget_max=45000,
        bhk_in=[1,2],
        furnishing_in=["Semi-Furnished","Fully Furnished","Unfurnished"],
        property_types_in=["Apartment","Independent House","Gated Community"],
        max_age_hours=48,
        area_coords=None,
        proximity_km=None,
    )
    assert ok is True
    assert prox is None
