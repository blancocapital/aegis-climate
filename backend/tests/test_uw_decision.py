from app.services.uw_decision import prepare_decision_payload


def test_prepare_decision_payload_create():
    payload = {
        "exposure_version_id": 1,
        "decision": "PROCEED",
        "conditions_json": ["Condition A"],
        "rationale_text": "All checks passed.",
    }
    result = prepare_decision_payload(None, payload)
    assert result["decision"] == "PROCEED"
    assert result["conditions_json"] == ["Condition A"]
    assert result["audit_metadata"]["action"] == "created"


def test_prepare_decision_payload_update_includes_previous():
    payload = {
        "exposure_version_id": 1,
        "decision": "REFER",
        "conditions_json": [],
        "rationale_text": "Missing data.",
    }
    result = prepare_decision_payload({"decision": "PROCEED"}, payload)
    assert result["decision"] == "REFER"
    assert result["audit_metadata"]["action"] == "updated"
    assert result["audit_metadata"]["previous_decision"] == "PROCEED"
