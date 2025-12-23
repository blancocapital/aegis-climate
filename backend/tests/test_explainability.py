from app.services.explainability import (
    build_explainability,
    narrative_summary,
    peril_contributions,
    structural_impacts,
)


def test_contribution_pct_sums_to_one():
    peril_scores = {
        "flood": {"adjusted": 0.5, "weight": 0.5},
        "wind": {"adjusted": 0.5, "weight": 0.5},
    }
    contributions = peril_contributions(peril_scores)
    total_pct = sum(item["contribution_pct"] for item in contributions)
    assert round(total_pct, 6) == 1.0


def test_contribution_sorting_ties():
    peril_scores = {
        "wind": {"adjusted": 0.2, "weight": 0.5},
        "flood": {"adjusted": 0.2, "weight": 0.5},
    }
    contributions = peril_contributions(peril_scores)
    assert contributions[0]["peril"] == "flood"
    assert contributions[1]["peril"] == "wind"


def test_structural_impacts_detects_adjustments():
    resilience_result = {
        "structural_adjustments": {
            "roof_material_bonus": 5,
            "roof_material": "metal",
            "flood_score_adjustment": -0.05,
            "wildfire_score_adjustment": 0.02,
        }
    }
    impacts = structural_impacts({"elevation_m": 12, "vegetation_proximity_m": 20}, resilience_result)
    types = {impact["type"] for impact in impacts}
    assert "roof_material_bonus" in types
    assert "peril_score_adjustment" in types


def test_narrative_includes_score_and_missing_peril():
    contributions = [
        {"peril": "flood", "contribution_pct": 0.4},
        {"peril": "wildfire", "contribution_pct": 0.3},
    ]
    narrative = narrative_summary(
        contributions,
        resilience_score=74,
        decision={"decision": "ACCEPT"},
        data_quality={"peril_missing": ["wind"]},
    )
    assert "Resilience 74" in narrative
    assert "Flood" in narrative
    assert "Wildfire" in narrative
    assert "missing wind score" in narrative.lower()


def test_build_explainability_output():
    resilience_result = {
        "resilience_score": 80,
        "peril_scores": {"flood": {"adjusted": 0.4, "weight": 0.5}},
        "structural_adjustments": {"roof_material_bonus": 0, "roof_material": "tile"},
    }
    explainability = build_explainability(
        resilience_result,
        hazards={"flood": {"score": 0.4}},
        structural_used={"roof_material": "tile"},
        decision=None,
        data_quality={"peril_missing": []},
    )
    assert "drivers" in explainability
    assert "structural_impacts" in explainability
    assert "narrative" in explainability
