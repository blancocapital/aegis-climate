from typing import Any, Dict, Optional


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_structural(structural: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not structural:
        return {}
    normalized: Dict[str, Any] = {}
    if "roof_material" in structural:
        roof = structural.get("roof_material")
        if isinstance(roof, str):
            roof_value = roof.strip()
            if roof_value:
                normalized["roof_material"] = roof_value
    if "elevation_m" in structural:
        elevation = _coerce_float(structural.get("elevation_m"))
        if elevation is not None:
            normalized["elevation_m"] = elevation
    if "vegetation_proximity_m" in structural:
        proximity = _coerce_float(structural.get("vegetation_proximity_m"))
        if proximity is not None:
            normalized["vegetation_proximity_m"] = proximity
    return normalized


def merge_structural(base: Optional[Dict[str, Any]], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base_norm = normalize_structural(base)
    override_norm = normalize_structural(override)
    merged = dict(base_norm)
    merged.update(override_norm)
    return merged
