from app.services.validation import validate_rows
from app.services.commit import canonicalize_rows
from app.services.validation import validate_rows


def test_validation_determinism():
    rows = [
        {"external_location_id": "A", "latitude": "1", "longitude": "2", "tiv": "100"},
        {"external_location_id": "", "latitude": "", "longitude": "", "tiv": "-1"},
    ]
    summary1, issues1, artifact1, checksum1 = validate_rows(rows, {})
    summary2, issues2, artifact2, checksum2 = validate_rows(rows, {})
    assert artifact1 == artifact2
    assert checksum1 == checksum2
    assert summary1 == summary2
    assert issues1 == issues2


def test_commit_ordering_stable():
    csv_bytes = b"external_location_id,latitude,longitude,tiv\nB,1,1,10\nA,2,2,20\n"
    rows = canonicalize_rows(csv_bytes, {})
    assert [r["external_location_id"] for r in rows] == ["A", "B"]
