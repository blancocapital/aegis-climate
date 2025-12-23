from typing import Any, Dict, List, Optional


DEFAULT_POLICY: Dict[str, Any] = {
    "score_accept_min": 70,
    "score_refer_min": 40,
    "decline_score_max": 39,
    "peril_decline_thresholds": {"flood": 0.90, "wildfire": 0.90},
    "peril_refer_thresholds": {"flood": 0.70, "wildfire": 0.70, "wind": 0.75, "heat": 0.80},
    "require_structural_fields": ["roof_material"],
    "max_missing_perils_for_accept": 0,
}

KNOWN_ROOF_MATERIALS = {"metal", "tile", "asphalt_shingle", "wood_shake"}
WEAK_ROOF_MATERIALS = {"wood_shake"}


def evaluate_underwriting_decision(
    resilience_result: Dict[str, Any],
    hazards: Dict[str, Dict[str, Any]],
    structural_used: Dict[str, Any],
    data_quality: Dict[str, Any],
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    policy_effective = dict(DEFAULT_POLICY)
    if policy:
        policy_effective.update({k: v for k, v in policy.items() if v is not None})

    score_accept_min = policy_effective.get("score_accept_min", 70)
    score_refer_min = policy_effective.get("score_refer_min", 40)
    decline_score_max = policy_effective.get("decline_score_max", 39)
    peril_decline = policy_effective.get("peril_decline_thresholds", {}) or {}
    peril_refer = policy_effective.get("peril_refer_thresholds", {}) or {}
    require_structural = policy_effective.get("require_structural_fields", []) or []
    max_missing_perils = policy_effective.get("max_missing_perils_for_accept", 0)

    resilience_score = resilience_result.get("resilience_score", 0)
    reason_codes: List[str] = []
    reasons: List[str] = []

    peril_missing = data_quality.get("peril_missing") or []
    used_unknown_fallback = bool(data_quality.get("used_unknown_hazard_fallback"))
    enrichment_status = data_quality.get("enrichment_status")
    enrichment_failed = bool(data_quality.get("enrichment_failed"))
    best_effort = bool(data_quality.get("best_effort"))

    if enrichment_failed and best_effort:
        reason_codes.append("ENRICHMENT_FAILED")
        reasons.append("Property enrichment failed; decision needs more data.")
        decision = "NEEDS_DATA"
    else:
        decision = None

    if decision is None:
        if resilience_score <= decline_score_max:
            reason_codes.append("SCORE_LOW_DECLINE")
            reasons.append("Resilience score is below decline threshold.")
            decision = "DECLINE"
        else:
            for peril, threshold in peril_decline.items():
                hazard_score = _peril_score(hazards, peril)
                if hazard_score is not None and hazard_score >= threshold:
                    code = f"PERIL_HIGH_DECLINE_{peril.upper()}"
                    reason_codes.append(code)
                    reasons.append(f"{peril} hazard exceeds decline threshold.")
                    decision = "DECLINE"
                    break

    if decision is None:
        if resilience_score < score_accept_min:
            reason_codes.append("SCORE_MEDIUM_REFER")
            reasons.append("Resilience score is below accept threshold.")
            decision = "REFER"
        else:
            for peril, threshold in peril_refer.items():
                hazard_score = _peril_score(hazards, peril)
                if hazard_score is not None and hazard_score >= threshold:
                    code = f"PERIL_ELEVATED_REFER_{peril.upper()}"
                    reason_codes.append(code)
                    reasons.append(f"{peril} hazard exceeds refer threshold.")
                    decision = "REFER"
                    break

    if decision is None:
        missing_count = len(peril_missing)
        required_missing = [field for field in require_structural if structural_used.get(field) is None]
        if missing_count > max_missing_perils or required_missing:
            if missing_count > max_missing_perils:
                reason_codes.append("MISSING_PERIL_DATA")
                reasons.append("Missing hazard data for required perils.")
            for field in required_missing:
                code = f"STRUCTURAL_MISSING_{field.upper()}"
                reason_codes.append(code)
                reasons.append(f"Missing required structural field: {field}.")
            decision = "NEEDS_DATA"

    if decision is None:
        decision = "ACCEPT"

    confidence = _compute_confidence(
        used_unknown_fallback=used_unknown_fallback,
        required_missing=[field for field in require_structural if structural_used.get(field) is None],
        enrichment_status=enrichment_status,
    )
    if confidence < 0.7:
        reason_codes.append("LOW_CONFIDENCE_DATA")
        reasons.append("Confidence is reduced due to data gaps.")

    mitigation_recommendations = _mitigation_recommendations(hazards, structural_used)

    return {
        "decision": decision,
        "confidence": confidence,
        "reason_codes": _unique_preserve(reason_codes),
        "reasons": _unique_preserve(reasons),
        "mitigation_recommendations": mitigation_recommendations,
        "policy_used": {
            "score_accept_min": score_accept_min,
            "score_refer_min": score_refer_min,
            "decline_score_max": decline_score_max,
            "peril_decline_thresholds": peril_decline,
            "peril_refer_thresholds": peril_refer,
            "require_structural_fields": require_structural,
            "max_missing_perils_for_accept": max_missing_perils,
        },
    }


def _peril_score(hazards: Dict[str, Dict[str, Any]], peril: str) -> Optional[float]:
    entry = hazards.get(peril) or {}
    score = entry.get("score")
    if isinstance(score, (int, float)):
        return float(score)
    return None


def _compute_confidence(
    used_unknown_fallback: bool,
    required_missing: List[str],
    enrichment_status: Optional[str],
) -> float:
    confidence = 1.0
    if used_unknown_fallback:
        confidence -= 0.15
    if required_missing:
        confidence -= 0.10
    if enrichment_status in ("queued", "failed"):
        confidence -= 0.10
    if confidence < 0:
        confidence = 0.0
    if confidence > 1:
        confidence = 1.0
    return round(confidence, 2)


def _mitigation_recommendations(
    hazards: Dict[str, Dict[str, Any]],
    structural_used: Dict[str, Any],
) -> List[Dict[str, Any]]:
    recommendations: List[Dict[str, Any]] = []
    wildfire_score = _peril_score(hazards, "wildfire")
    vegetation = structural_used.get("vegetation_proximity_m")
    if (wildfire_score is not None and wildfire_score >= 0.70) or (
        isinstance(vegetation, (int, float)) and vegetation <= 30
    ):
        recommendations.append(
            {
                "code": "MIT_WILDFIRE_DEFENSIBLE_SPACE",
                "title": "Improve defensible space",
                "detail": "Create defensible space and manage nearby vegetation within 30 meters.",
                "applies_to": ["wildfire"],
            }
        )

    flood_score = _peril_score(hazards, "flood")
    elevation = structural_used.get("elevation_m")
    if (flood_score is not None and flood_score >= 0.70) or elevation is None or (
        isinstance(elevation, (int, float)) and elevation <= 5
    ):
        recommendations.append(
            {
                "code": "MIT_FLOOD_ELEVATION_DRAINAGE",
                "title": "Improve flood resilience",
                "detail": "Consider flood vents, elevation verification, and drainage improvements.",
                "applies_to": ["flood"],
            }
        )

    wind_score = _peril_score(hazards, "wind")
    roof_material = structural_used.get("roof_material")
    roof_unknown = roof_material is None or roof_material not in KNOWN_ROOF_MATERIALS
    roof_weak = roof_material in WEAK_ROOF_MATERIALS
    if (wind_score is not None and wind_score >= 0.75) or roof_unknown or roof_weak:
        recommendations.append(
            {
                "code": "MIT_WIND_ROOF_HARDENING",
                "title": "Harden roof against wind",
                "detail": "Inspect roof, add tie-downs, and verify fastening for wind resilience.",
                "applies_to": ["wind"],
            }
        )

    return recommendations


def _unique_preserve(items: List[str]) -> List[str]:
    seen = set()
    output = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output
