from app.services.rollup import compute_rollup
from app.services.breaches import evaluate_rule_on_rollup_rows


def test_compute_rollup_deterministic():
    records = [
        {"country": "US", "hazard_band": "HIGH", "tiv": 100, "lob": "prop"},
        {"country": "US", "hazard_band": "LOW", "tiv": 50, "lob": "prop"},
        {"country": "CA", "hazard_band": "HIGH", "tiv": 30, "lob": "prop"},
    ]
    dims = ["country", "hazard_band"]
    measures = [
        {"name": "tiv_sum", "op": "sum", "field": "tiv"},
        {"name": "location_count", "op": "count"},
    ]
    rows1, checksum1 = compute_rollup(records, dims, measures)
    rows2, checksum2 = compute_rollup(list(reversed(records)), dims, measures)
    assert rows1 == rows2
    assert checksum1 == checksum2


def test_compute_rollup_filters_and_hazard_dims():
    records = [
        {"country": "US", "hazard_band": "HIGH", "tiv": 100, "lob": "prop"},
        {"country": "US", "hazard_band": "LOW", "tiv": 50, "lob": "prop"},
        {"country": "CA", "hazard_band": "HIGH", "tiv": 30, "lob": "prop"},
    ]
    dims = ["country", "hazard_band"]
    measures = [{"name": "tiv_sum", "op": "sum", "field": "tiv"}]
    rows, _ = compute_rollup(records, dims, measures, filters={"country": "US"})
    assert len(rows) == 2
    assert all(r["rollup_key_json"]["country"] == "US" for r in rows)


def test_evaluate_rule_on_rollup_rows():
    rows, _ = compute_rollup(
        [
            {"country": "US", "hazard_band": "HIGH", "tiv": 120},
            {"country": "US", "hazard_band": "LOW", "tiv": 10},
        ],
        ["country", "hazard_band"],
        [{"name": "tiv_sum", "op": "sum", "field": "tiv"}],
    )
    rule = {"metric": "tiv_sum", "operator": ">", "value": 50, "where": {"country": "US"}}
    matches = evaluate_rule_on_rollup_rows(rows, rule)
    assert len(matches) == 1
    rule_strict = {"metric": "tiv_sum", "operator": ">", "value": 100, "where": {"hazard_band": "HIGH"}}
    matches2 = evaluate_rule_on_rollup_rows(rows, rule_strict)
    assert len(matches2) == 1
