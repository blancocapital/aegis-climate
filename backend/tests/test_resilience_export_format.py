import csv
import io
import json

from app.services.resilience_export import CSV_COLUMNS, rows_to_csv


def test_export_header_and_json_serialization():
    row = {
        "location_id": 1,
        "external_location_id": "LOC-1",
        "latitude": 10.5,
        "longitude": -70.2,
        "address_line1": "123 Main",
        "city": "City",
        "state_region": "CA",
        "postal_code": "94107",
        "country": "US",
        "lob": "PROPERTY",
        "tiv": 1000000.0,
        "resilience_score": 88,
        "risk_score": 0.12,
        "warnings": ["missing hazard data for wind"],
        "hazards_json": {"wind": {"score": 0.2}},
        "structural_json": {"roof_material": "metal"},
        "input_structural_json": {"roof_material": "metal"},
    }
    csv_text = rows_to_csv([row])
    reader = csv.reader(io.StringIO(csv_text))
    header = next(reader)
    data = next(reader)
    assert header == CSV_COLUMNS
    col_index = {name: i for i, name in enumerate(header)}
    assert data[col_index["warnings"]] == "missing hazard data for wind"
    assert data[col_index["hazards_json"]] == json.dumps({"wind": {"score": 0.2}}, separators=(",", ":"), sort_keys=True)
    assert data[col_index["structural_json"]] == json.dumps({"roof_material": "metal"}, separators=(",", ":"), sort_keys=True)
    assert data[col_index["input_structural_json"]] == json.dumps({"roof_material": "metal"}, separators=(",", ":"), sort_keys=True)
