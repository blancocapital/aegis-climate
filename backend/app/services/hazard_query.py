from typing import Any, Dict, Optional


def coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_hazard_entry(
    properties: Dict[str, Any],
    dataset_peril: Optional[str],
    dataset_name: str,
    version_label: str,
) -> Dict[str, Any]:
    props = properties or {}
    peril_value = props.get("hazard_category")
    if peril_value is None:
        peril_value = dataset_peril
    peril = str(peril_value).strip().lower() if peril_value is not None else None
    score_value = props.get("score")
    if score_value is None:
        score_value = props.get("Score")
    band = props.get("band") or props.get("Band")
    return {
        "peril": peril,
        "score": coerce_float(score_value),
        "band": band,
        "source": f"{dataset_name}:{version_label}",
        "raw": props,
    }


def merge_worst_in_peril(
    hazards: Dict[str, Dict[str, Any]],
    entry: Dict[str, Any],
    tie_breaker_id: Optional[int] = None,
) -> Dict[str, Dict[str, Any]]:
    peril = entry.get("peril")
    if not peril:
        return hazards
    entry_score = coerce_float(entry.get("score"))
    existing = hazards.get(peril)
    if existing is None:
        stored = dict(entry)
        if tie_breaker_id is not None:
            stored["_tie_breaker_id"] = tie_breaker_id
        hazards[peril] = stored
        return hazards

    existing_score = coerce_float(existing.get("score"))
    if entry_score is None and existing_score is None:
        return hazards
    if existing_score is None and entry_score is not None:
        stored = dict(entry)
        if tie_breaker_id is not None:
            stored["_tie_breaker_id"] = tie_breaker_id
        hazards[peril] = stored
        return hazards
    if entry_score is None:
        return hazards

    if existing_score is None or entry_score > existing_score:
        stored = dict(entry)
        if tie_breaker_id is not None:
            stored["_tie_breaker_id"] = tie_breaker_id
        hazards[peril] = stored
        return hazards

    if entry_score < existing_score:
        return hazards

    if tie_breaker_id is None:
        return hazards
    existing_id = existing.get("_tie_breaker_id")
    if existing_id is None:
        return hazards
    if tie_breaker_id < existing_id:
        stored = dict(entry)
        stored["_tie_breaker_id"] = tie_breaker_id
        hazards[peril] = stored
    return hazards
