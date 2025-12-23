from app.services.property_enrichment import address_fingerprint, map_to_structural, normalize_address
from app.services.structural import merge_structural


def test_normalize_address_deterministic():
    addr = {
        "address_line1": " 123 Main ",
        "city": "City",
        "state_region": "ca",
        "postal_code": "94107 ",
        "country": "us",
    }
    first = normalize_address(addr)
    second = normalize_address(addr)
    assert first == second


def test_address_fingerprint_stable():
    addr = normalize_address(
        {"address_line1": "123 Main", "city": "City", "state_region": "CA", "postal_code": "94107", "country": "US"}
    )
    assert address_fingerprint(addr) == address_fingerprint(addr)


def test_map_to_structural_canonical_keys():
    structural, provenance = map_to_structural(
        {"roof_material": "metal", "extra": "noop", "field_confidence": {"roof_material": 0.8}, "provider": "stub"},
        {"parcel_id": "P", "provider": "stub"},
        {"provider": "stub"},
    )
    assert set(structural.keys()).issubset({"roof_material", "elevation_m", "vegetation_proximity_m"})
    assert "roof_material" in provenance


def test_merge_precedence_profile_vs_payload():
    profile_struct = {"roof_material": "tile", "elevation_m": 10}
    payload_struct = {"roof_material": "metal"}
    merged = merge_structural(profile_struct, payload_struct)
    assert merged == {"roof_material": "metal", "elevation_m": 10}


def test_field_provenance_structure():
    _, provenance = map_to_structural(
        {"roof_material": "metal", "field_confidence": {"roof_material": 0.8}, "provider": "stub"},
        {},
        {},
    )
    assert "roof_material" in provenance
    assert "confidence" in provenance["roof_material"]
