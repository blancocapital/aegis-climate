from app.services.hazard_query import coerce_float, extract_hazard_entry, merge_worst_in_peril


def test_merge_worst_in_peril_selects_higher_score():
    hazards = {}
    merge_worst_in_peril(hazards, {"peril": "flood", "score": 0.3})
    merge_worst_in_peril(hazards, {"peril": "flood", "score": 0.6})
    assert hazards["flood"]["score"] == 0.6


def test_merge_worst_in_peril_numeric_beats_none():
    hazards = {}
    merge_worst_in_peril(hazards, {"peril": "wind", "score": None})
    merge_worst_in_peril(hazards, {"peril": "wind", "score": 0.2})
    assert hazards["wind"]["score"] == 0.2


def test_merge_worst_in_peril_tie_determinism():
    hazards = {}
    merge_worst_in_peril(hazards, {"peril": "heat", "score": None, "source": "a"})
    merge_worst_in_peril(hazards, {"peril": "heat", "score": None, "source": "b"})
    assert hazards["heat"]["source"] == "a"

    hazards = {}
    merge_worst_in_peril(hazards, {"peril": "flood", "score": 0.5, "source": "first"}, tie_breaker_id=10)
    merge_worst_in_peril(hazards, {"peril": "flood", "score": 0.5, "source": "second"}, tie_breaker_id=5)
    assert hazards["flood"]["source"] == "second"


def test_extract_hazard_entry_prefers_hazard_category():
    entry = extract_hazard_entry(
        {"hazard_category": "wildfire", "score": 0.4, "band": "HIGH"},
        dataset_peril="flood",
        dataset_name="Demo",
        version_label="v1",
    )
    assert entry["peril"] == "wildfire"


def test_coerce_float_handles_strings_and_invalid():
    assert coerce_float("0.7") == 0.7
    assert coerce_float("nope") is None
