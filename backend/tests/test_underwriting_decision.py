from app.services.underwriting_decision import evaluate_underwriting_decision


def _base_inputs():
    resilience = {"resilience_score": 80}
    hazards = {"flood": {"score": 0.2}, "wildfire": {"score": 0.2}, "wind": {"score": 0.2}, "heat": {"score": 0.2}}
    structural = {"roof_material": "metal", "elevation_m": 10, "vegetation_proximity_m": 50}
    data_quality = {
        "peril_missing": [],
        "used_unknown_hazard_fallback": False,
        "enrichment_status": "used_profile",
        "enrichment_failed": False,
        "best_effort": True,
    }
    return resilience, hazards, structural, data_quality


def test_decline_when_score_low():
    resilience, hazards, structural, data_quality = _base_inputs()
    resilience["resilience_score"] = 30
    decision = evaluate_underwriting_decision(resilience, hazards, structural, data_quality)
    assert decision["decision"] == "DECLINE"
    assert "SCORE_LOW_DECLINE" in decision["reason_codes"]


def test_decline_when_peril_high():
    resilience, hazards, structural, data_quality = _base_inputs()
    hazards["flood"]["score"] = 0.95
    decision = evaluate_underwriting_decision(resilience, hazards, structural, data_quality)
    assert decision["decision"] == "DECLINE"
    assert "PERIL_HIGH_DECLINE_FLOOD" in decision["reason_codes"]


def test_refer_when_score_mid():
    resilience, hazards, structural, data_quality = _base_inputs()
    resilience["resilience_score"] = 55
    decision = evaluate_underwriting_decision(resilience, hazards, structural, data_quality)
    assert decision["decision"] == "REFER"
    assert "SCORE_MEDIUM_REFER" in decision["reason_codes"]


def test_refer_when_peril_elevated():
    resilience, hazards, structural, data_quality = _base_inputs()
    hazards["wind"]["score"] = 0.8
    decision = evaluate_underwriting_decision(resilience, hazards, structural, data_quality)
    assert decision["decision"] == "REFER"
    assert "PERIL_ELEVATED_REFER_WIND" in decision["reason_codes"]


def test_needs_data_when_missing_perils():
    resilience, hazards, structural, data_quality = _base_inputs()
    data_quality["peril_missing"] = ["flood"]
    decision = evaluate_underwriting_decision(resilience, hazards, structural, data_quality)
    assert decision["decision"] == "NEEDS_DATA"
    assert "MISSING_PERIL_DATA" in decision["reason_codes"]


def test_needs_data_when_required_structural_missing():
    resilience, hazards, structural, data_quality = _base_inputs()
    structural["roof_material"] = None
    decision = evaluate_underwriting_decision(resilience, hazards, structural, data_quality)
    assert decision["decision"] == "NEEDS_DATA"
    assert "STRUCTURAL_MISSING_ROOF_MATERIAL" in decision["reason_codes"]


def test_confidence_reduces_on_unknown_fallback_and_enrichment_failed():
    resilience, hazards, structural, data_quality = _base_inputs()
    data_quality["used_unknown_hazard_fallback"] = True
    data_quality["enrichment_status"] = "failed"
    data_quality["enrichment_failed"] = True
    decision = evaluate_underwriting_decision(resilience, hazards, structural, data_quality)
    assert decision["confidence"] < 1.0


def test_mitigation_recommendations():
    resilience, hazards, structural, data_quality = _base_inputs()
    hazards["wildfire"]["score"] = 0.75
    structural["vegetation_proximity_m"] = 20
    hazards["flood"]["score"] = 0.75
    structural["elevation_m"] = None
    hazards["wind"]["score"] = 0.8
    structural["roof_material"] = "wood_shake"
    decision = evaluate_underwriting_decision(resilience, hazards, structural, data_quality)
    codes = {rec["code"] for rec in decision["mitigation_recommendations"]}
    assert "MIT_WILDFIRE_DEFENSIBLE_SPACE" in codes
    assert "MIT_FLOOD_ELEVATION_DRAINAGE" in codes
    assert "MIT_WIND_ROOF_HARDENING" in codes
