from app.services.structural import merge_structural, normalize_structural


def test_normalize_structural_drops_unknown_keys():
    result = normalize_structural({"roof_material": "metal", "foo": "bar"})
    assert result == {"roof_material": "metal"}


def test_normalize_structural_numeric_coercion():
    result = normalize_structural({"elevation_m": "12.3", "vegetation_proximity_m": "7"})
    assert result == {"elevation_m": 12.3, "vegetation_proximity_m": 7.0}


def test_merge_structural_override_precedence():
    base = {"roof_material": "tile", "elevation_m": 10}
    override = {"roof_material": "metal"}
    assert merge_structural(base, override) == {"roof_material": "metal", "elevation_m": 10}


def test_structural_determinism():
    payload = {"roof_material": "metal", "elevation_m": "10"}
    first = normalize_structural(payload)
    second = normalize_structural(payload)
    assert first == second
