from app.services.drift import compare_exposures


def test_drift_classification_and_checksum():
    a_rows = [
        {"external_location_id": "A", "tiv": 100, "city": "X"},
        {"external_location_id": "B", "tiv": 50, "city": "Y"},
    ]
    b_rows = [
        {"external_location_id": "B", "tiv": 60, "city": "Z"},
        {"external_location_id": "C", "tiv": 70, "city": "Y"},
    ]
    summary, details, artifact, checksum = compare_exposures(a_rows, b_rows, {})
    assert summary == {"NEW": 1, "REMOVED": 1, "MODIFIED": 1, "total": 3}
    assert [d["classification"] for d in details] == ["NEW", "REMOVED", "MODIFIED"]
    modified = [d for d in details if d["classification"] == "MODIFIED"][0]
    assert "tiv" in modified["delta_json"]["changes"]
    # deterministic checksum even with shuffled input
    summary2, details2, artifact2, checksum2 = compare_exposures(list(reversed(a_rows)), list(reversed(b_rows)), {})
    assert details == details2
    assert artifact == artifact2
    assert checksum == checksum2
