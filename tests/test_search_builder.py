from nobroker_watchdog.scraper.search_builder import build_search_targets


def test_build_search_targets_includes_filters():
    targets = build_search_targets(
        city="Bangalore",
        areas=["Kadubeesanahalli, Bangalore"],
        area_coords={"Kadubeesanahalli, Bangalore": (12.9354, 77.6974)},
        bhk_in=[1, 2, 3],
        furnishing_in=["Semi-Furnished", "Fully Furnished"],
        carpet_min_sqft=500,
        floors_allowed_in=["4+"],
        proximity_km=2.0,
    )
    html_target = next(t for t in targets if t.kind == "html" and "searchParam" in t.url)
    assert "radius=2.0" in html_target.url
    assert "type=BHK1,BHK2,BHK3" in html_target.url
    assert "furnishing=SEMI_FURNISHED,FULLY_FURNISHED" in html_target.url
    assert "farea=500,10000" in html_target.url
    assert "floor=4+" in html_target.url
