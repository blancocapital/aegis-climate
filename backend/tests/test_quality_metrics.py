from app.services.quality_metrics import compute_bucket_percentages, init_peril_coverage, update_peril_coverage


def test_peril_coverage_updates():
    coverage = init_peril_coverage(["flood", "wind"])
    hazards = {"flood": {"score": 0.3}, "wind": {"score": None}}
    update_peril_coverage(coverage, hazards, ["flood", "wind"])
    assert coverage["flood"]["with_score"] == 1
    assert coverage["flood"]["missing_score"] == 0
    assert coverage["wind"]["with_score"] == 0
    assert coverage["wind"]["missing_score"] == 1


def test_bucket_percentages():
    buckets = {"0_19": 1, "20_39": 1}
    assert compute_bucket_percentages(buckets, 2) == {"0_19": 0.5, "20_39": 0.5}
    assert compute_bucket_percentages(buckets, 0) == {"0_19": 0.0, "20_39": 0.0}
