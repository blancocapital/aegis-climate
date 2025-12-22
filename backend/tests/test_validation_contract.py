from app.services.validation import validate_rows


def test_currency_and_segmentation_rules():
    rows = [
        {
            "external_location_id": "1",
            "address_line1": "123",
            "city": "City",
            "state_region": "CA",
            "postal_code": "90001",
            "country": "US",
            "tiv": "100",
            "lob": "",
            "product_code": "",
            "currency": "",
        }
    ]
    summary, issues, artifact, checksum = validate_rows(rows, {})
    assert summary["ERROR"] == 1
    assert summary["WARN"] == 1
    codes = {i["code"] for i in issues}
    assert "MISSING_SEGMENTATION" in codes
    assert "MISSING_CURRENCY_DEFAULTED" in codes
    # determinism
    summary2, issues2, artifact2, checksum2 = validate_rows(rows, {})
    assert artifact == artifact2
    assert checksum == checksum2
    assert issues == issues2
