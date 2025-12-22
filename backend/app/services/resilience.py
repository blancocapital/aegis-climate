from typing import Any, Dict, Optional

DEFAULT_WEIGHTS = {
    "flood": 0.35,
    "wildfire": 0.35,
    "wind": 0.15,
    "heat": 0.15,
}
DEFAULT_UNKNOWN_HAZARD_SCORE = 0.5
ROOF_MATERIAL_BONUS = {
    "metal": 5,
    "tile": 3,
    "asphalt_shingle": 0,
    "wood_shake": -5,
}


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _coerce_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_resilience_score(
    hazards: Dict[str, Dict[str, Any]],
    structural: Optional[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    hazards = hazards or {}
    structural = structural or {}
    config = config or {}

    weights = dict(DEFAULT_WEIGHTS)
    if isinstance(config.get("weights"), dict):
        weights.update(config["weights"])
    unknown_hazard_score = _coerce_float(config.get("unknown_hazard_score"))
    if unknown_hazard_score is None:
        unknown_hazard_score = DEFAULT_UNKNOWN_HAZARD_SCORE

    roof_material = structural.get("roof_material")
    roof_key = roof_material.strip().lower() if isinstance(roof_material, str) else None
    roof_bonus = ROOF_MATERIAL_BONUS.get(roof_key, 0)

    elevation_m = _coerce_float(structural.get("elevation_m"))
    vegetation_proximity_m = _coerce_float(structural.get("vegetation_proximity_m"))

    peril_scores: Dict[str, Dict[str, float]] = {}
    warnings = []
    flood_adjustment = None
    wildfire_adjustment = None

    risk = 0.0
    for peril, weight in weights.items():
        hazard_entry = hazards.get(peril)
        raw_score = hazard_entry.get("score") if hazard_entry else None
        if hazard_entry is None:
            warnings.append(f"missing hazard data for {peril}")
        elif raw_score is None:
            warnings.append(f"missing hazard score for {peril}")

        peril_score = raw_score if raw_score is not None else unknown_hazard_score
        peril_score = clamp(peril_score, 0.0, 1.0)
        adjusted_score = peril_score

        if peril == "flood" and elevation_m is not None:
            flood_delta = min(0.15, max(0.0, elevation_m) / 1000.0 * 0.10)
            adjusted_score = clamp(peril_score - flood_delta, 0.0, 1.0)
            flood_adjustment = -flood_delta
        elif peril == "wildfire" and vegetation_proximity_m is not None:
            distance = max(0.0, vegetation_proximity_m)
            if distance <= 30.0:
                wildfire_delta = (30.0 - distance) / 30.0 * 0.10
            else:
                wildfire_delta = 0.0
            adjusted_score = clamp(peril_score + wildfire_delta, 0.0, 1.0)
            wildfire_adjustment = wildfire_delta

        peril_scores[peril] = {
            "raw": peril_score,
            "adjusted": adjusted_score,
            "weight": float(weight),
        }
        risk += weight * adjusted_score

    risk_score = round(clamp(risk, 0.0, 1.0), 4)
    base_score = round(100 * (1 - risk_score))
    resilience_score = max(0, min(100, int(base_score + roof_bonus)))

    structural_adjustments = {
        "roof_material": roof_key,
        "roof_material_bonus": roof_bonus,
    }
    if flood_adjustment is not None:
        structural_adjustments["flood_score_adjustment"] = flood_adjustment
    if wildfire_adjustment is not None:
        structural_adjustments["wildfire_score_adjustment"] = wildfire_adjustment

    return {
        "resilience_score": resilience_score,
        "risk_score": risk_score,
        "peril_scores": peril_scores,
        "structural_adjustments": structural_adjustments,
        "warnings": warnings,
    }
