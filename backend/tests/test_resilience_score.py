import pytest

from app.services.resilience import compute_resilience_score


def test_resilience_score_deterministic():
    hazards = {
        "flood": {"score": 0.4, "band": "MED", "source": "demo", "raw": {}},
        "wildfire": {"score": 0.3, "band": "LOW", "source": "demo", "raw": {}},
        "wind": {"score": 0.2, "band": "LOW", "source": "demo", "raw": {}},
        "heat": {"score": 0.1, "band": "LOW", "source": "demo", "raw": {}},
    }
    structural = {"roof_material": "metal", "elevation_m": 200, "vegetation_proximity_m": 50}
    first = compute_resilience_score(hazards, structural, None)
    second = compute_resilience_score(hazards, structural, None)
    assert first == second


def test_missing_hazard_uses_unknown_score_and_warning():
    hazards = {"flood": {"score": 0.8, "band": "HIGH", "source": "demo", "raw": {}}}
    result = compute_resilience_score(hazards, {}, None)
    assert result["peril_scores"]["wind"]["raw"] == 0.5
    assert "missing hazard data for wind" in result["warnings"]


def test_roof_material_bonus_changes_score():
    hazards = {
        "flood": {"score": 0.2, "band": "LOW", "source": "demo", "raw": {}},
        "wildfire": {"score": 0.2, "band": "LOW", "source": "demo", "raw": {}},
        "wind": {"score": 0.2, "band": "LOW", "source": "demo", "raw": {}},
        "heat": {"score": 0.2, "band": "LOW", "source": "demo", "raw": {}},
    }
    metal = compute_resilience_score(hazards, {"roof_material": "metal"}, None)
    wood = compute_resilience_score(hazards, {"roof_material": "wood_shake"}, None)
    assert metal["resilience_score"] - wood["resilience_score"] == 10


def test_elevation_reduces_flood_score():
    hazards = {
        "flood": {"score": 0.8, "band": "HIGH", "source": "demo", "raw": {}},
        "wildfire": {"score": 0.0, "band": "LOW", "source": "demo", "raw": {}},
        "wind": {"score": 0.0, "band": "LOW", "source": "demo", "raw": {}},
        "heat": {"score": 0.0, "band": "LOW", "source": "demo", "raw": {}},
    }
    result = compute_resilience_score(hazards, {"elevation_m": 1000}, None)
    assert result["peril_scores"]["flood"]["adjusted"] == pytest.approx(0.7)


def test_vegetation_proximity_increases_wildfire_score():
    hazards = {
        "flood": {"score": 0.0, "band": "LOW", "source": "demo", "raw": {}},
        "wildfire": {"score": 0.4, "band": "MED", "source": "demo", "raw": {}},
        "wind": {"score": 0.0, "band": "LOW", "source": "demo", "raw": {}},
        "heat": {"score": 0.0, "band": "LOW", "source": "demo", "raw": {}},
    }
    result = compute_resilience_score(hazards, {"vegetation_proximity_m": 0}, None)
    assert result["peril_scores"]["wildfire"]["adjusted"] == pytest.approx(0.5)
