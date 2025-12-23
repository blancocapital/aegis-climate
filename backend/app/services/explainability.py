from typing import Any, Dict, List, Optional


def peril_contributions(peril_scores: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    contributions: List[Dict[str, Any]] = []
    total = 0.0
    for peril, scores in (peril_scores or {}).items():
        weight = float(scores.get("weight") or 0.0)
        adjusted = float(scores.get("adjusted") or 0.0)
        contribution = weight * adjusted
        contributions.append(
            {
                "peril": peril,
                "weight": weight,
                "adjusted_score": adjusted,
                "contribution": round(contribution, 6),
            }
        )
        total += contribution

    if total > 0:
        for item in contributions:
            item["contribution_pct"] = round(item["contribution"] / total, 6)
    else:
        for item in contributions:
            item["contribution_pct"] = 0.0

    contributions.sort(key=lambda x: (-x["contribution"], x["peril"]))
    return contributions


def structural_impacts(
    structural_used: Dict[str, Any],
    resilience_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    impacts: List[Dict[str, Any]] = []
    adjustments = resilience_result.get("structural_adjustments") or {}

    roof_bonus = adjustments.get("roof_material_bonus")
    roof_material = adjustments.get("roof_material")
    if roof_bonus is not None and roof_bonus != 0:
        impacts.append(
            {
                "type": "roof_material_bonus",
                "roof_material": roof_material,
                "points": int(roof_bonus),
            }
        )

    if "flood_score_adjustment" in adjustments:
        impacts.append(
            {
                "type": "peril_score_adjustment",
                "peril": "flood",
                "delta": float(adjustments.get("flood_score_adjustment") or 0.0),
                "source": "elevation_m",
                "input": structural_used.get("elevation_m"),
            }
        )

    if "wildfire_score_adjustment" in adjustments:
        impacts.append(
            {
                "type": "peril_score_adjustment",
                "peril": "wildfire",
                "delta": float(adjustments.get("wildfire_score_adjustment") or 0.0),
                "source": "vegetation_proximity_m",
                "input": structural_used.get("vegetation_proximity_m"),
            }
        )

    return impacts


def narrative_summary(
    contributions: List[Dict[str, Any]],
    resilience_score: int,
    decision: Optional[Dict[str, Any]],
    data_quality: Dict[str, Any],
) -> str:
    parts: List[str] = []
    decision_value = decision.get("decision") if isinstance(decision, dict) else None
    if decision_value:
        parts.append(f"Resilience {resilience_score} ({decision_value}).")
    else:
        parts.append(f"Resilience {resilience_score}.")

    top = contributions[:2]
    if top:
        formatted = []
        for item in top:
            pct = int(round(item.get("contribution_pct", 0.0) * 100))
            formatted.append(f"{_format_peril(item.get('peril'))} ({pct}%)")
        parts.append(f"Top drivers: {', '.join(formatted)}.")

    missing = data_quality.get("peril_missing") or []
    if missing:
        missing_names = ", ".join([_format_peril(peril).lower() for peril in missing])
        suffix = "scores" if len(missing) > 1 else "score"
        parts.append(f"Data gaps: missing {missing_names} {suffix}.")

    narrative = " ".join(parts)
    if len(narrative) > 300:
        narrative = narrative[:297].rstrip() + "..."
    return narrative


def build_explainability(
    resilience_result: Dict[str, Any],
    hazards: Dict[str, Any],
    structural_used: Dict[str, Any],
    decision: Optional[Dict[str, Any]],
    data_quality: Dict[str, Any],
) -> Dict[str, Any]:
    peril_scores = resilience_result.get("peril_scores") or {}
    drivers = peril_contributions(peril_scores)
    impacts = structural_impacts(structural_used or {}, resilience_result or {})
    narrative = narrative_summary(
        drivers,
        int(resilience_result.get("resilience_score") or 0),
        decision,
        data_quality or {},
    )
    return {
        "drivers": drivers,
        "structural_impacts": impacts,
        "narrative": narrative,
    }


def _format_peril(peril: Optional[str]) -> str:
    if not peril:
        return "Unknown"
    return str(peril).replace("_", " ").title()
