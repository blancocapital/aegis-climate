from app.services.geocode import geocode_address
from app.services.quality import quality_scores


def test_geocode_stub_deterministic():
    a1 = geocode_address("123 Main", "City", "US")
    a2 = geocode_address("123 Main", "City", "US")
    assert a1 == a2


def test_quality_tiers():
    scores = quality_scores({"address_line1": "123", "tiv": 100, "geocode_confidence": 0.8})
    assert scores["quality_tier"] == "A"
    low_scores = quality_scores({"address_line1": None, "tiv": None, "geocode_confidence": 0.2})
    assert low_scores["quality_tier"] == "C"
