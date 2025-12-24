from app.services.uw_rules import build_location_record, evaluate_predicate, evaluate_rule


def test_predicate_numeric_ops():
    record = {"tiv": "1000"}
    assert evaluate_predicate({"field": "tiv", "op": ">=", "value": 500}, record)["matched"]
    assert not evaluate_predicate({"field": "tiv", "op": "<", "value": 100}, record)["matched"]


def test_predicate_in_and_exists():
    record = {"hazard_band": ["HIGH", "MEDIUM"], "state_region": "CA"}
    assert evaluate_predicate({"field": "hazard_band", "op": "in", "value": ["HIGH"]}, record)["matched"]
    assert evaluate_predicate({"field": "state_region", "op": "exists"}, record)["matched"]
    assert not evaluate_predicate({"field": "hazard_band", "op": "not_in", "value": ["HIGH"]}, record)["matched"]


def test_location_record_determinism():
    class DummyLocation:
        id = 1
        external_location_id = "L1"
        tiv = 100
        country = "US"
        state_region = "CA"
        postal_code = "94103"
        lob = "GL"
        product_code = "PROD"
        currency = "USD"
        quality_tier = "B"
        geocode_confidence = 0.8

    hazard_entries_a = [{"band": "HIGH"}, {"band": "LOW"}, {"hazard_category": "flood"}]
    hazard_entries_b = [{"hazard_category": "flood"}, {"band": "LOW"}, {"band": "HIGH"}]
    record_a = build_location_record(DummyLocation, hazard_entries_a)
    record_b = build_location_record(DummyLocation, hazard_entries_b)
    assert record_a["hazard_band"] == record_b["hazard_band"]
    assert record_a["hazard_category"] == record_b["hazard_category"]


def test_rule_evaluation_determinism_for_lists():
    rule = {
        "when": {"all": [{"field": "hazard_band", "op": "in", "value": ["HIGH"]}]},
        "then": {"disposition": "REFER"},
    }
    record_a = {"hazard_band": ["LOW", "HIGH"]}
    record_b = {"hazard_band": ["HIGH", "LOW"]}
    matched_a, explanation_a = evaluate_rule(rule, record_a)
    matched_b, explanation_b = evaluate_rule(rule, record_b)
    assert matched_a and matched_b
    assert explanation_a == explanation_b
