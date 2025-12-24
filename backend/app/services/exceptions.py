import hashlib
import json
from typing import Any, Dict, Tuple


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def exception_key(exposure_version_id: int, exception_type: str, details: Dict[str, Any]) -> str:
    if exception_type == "VALIDATION_ISSUE":
        row_number = details.get("row_number", 0)
        code = details.get("code", "UNKNOWN")
        return f"validation:{exposure_version_id}:{row_number}:{code}"
    if exception_type in {"QUALITY_TIER_C", "LOW_GEO_CONFIDENCE"}:
        location_id = details.get("location_id") or details.get("external_location_id") or "unknown"
        return f"location:{exposure_version_id}:{location_id}:{exception_type}"
    payload = _canonical_json(details)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:12]
    return f"exception:{exposure_version_id}:{exception_type}:{digest}"


def exception_impact_and_action(exception_type: str, details: Dict[str, Any]) -> Tuple[str, str]:
    if exception_type == "VALIDATION_ISSUE":
        code = details.get("code", "")
        if code == "MISSING_LOCATION":
            return (
                "Location is incomplete; downstream hazards and scores may be unavailable.",
                "Provide lat/lon or full address fields.",
            )
        if code == "MISSING_TIV":
            return (
                "Financial exposure is missing; accumulations and controls are incomplete.",
                "Provide a valid TIV for the location.",
            )
        if code == "MISSING_SEGMENTATION":
            return (
                "Segmentation is missing; rollups and portfolio controls may be blocked.",
                "Provide LOB or product_code.",
            )
        return (
            "Validation issue affects data quality and downstream analytics.",
            "Correct the invalid or missing field.",
        )
    if exception_type == "QUALITY_TIER_C":
        return (
            "Low data quality tier may reduce confidence in underwriting outputs.",
            "Improve missing COPE or geocode inputs and re-run enrichment.",
        )
    if exception_type == "LOW_GEO_CONFIDENCE":
        return (
            "Low geocode confidence may place the risk in the wrong hazard zone.",
            "Verify address or provide precise coordinates.",
        )
    return (
        "Exception may impact underwriting decisions.",
        "Review and resolve the flagged data issue.",
    )


def parse_exception_key(exception_key_value: str) -> int | None:
    parts = exception_key_value.split(":", 3)
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except (TypeError, ValueError):
        return None
