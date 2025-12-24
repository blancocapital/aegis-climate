from typing import Any, Dict, Optional


def prepare_decision_payload(existing: Optional[Dict[str, Any]], payload: Dict[str, Any]) -> Dict[str, Any]:
    action = "updated" if existing else "created"
    audit_metadata = {
        "exposure_version_id": payload.get("exposure_version_id"),
        "action": action,
    }
    if existing:
        audit_metadata["previous_decision"] = existing.get("decision")
    return {
        "decision": payload.get("decision"),
        "conditions_json": payload.get("conditions_json") or [],
        "rationale_text": payload.get("rationale_text"),
        "audit_metadata": audit_metadata,
    }
