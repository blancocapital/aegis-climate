from app.services.resilience_summary import bucket_counts


def test_bucket_counts_boundaries():
    scores = [19, 20, 39, 40, 59, 60, 79, 80, 100]
    buckets = bucket_counts(scores)
    assert buckets == {
        "0_19": 1,
        "20_39": 2,
        "40_59": 2,
        "60_79": 2,
        "80_100": 2,
    }


def test_bucket_counts_empty():
    assert bucket_counts([]) == {
        "0_19": 0,
        "20_39": 0,
        "40_59": 0,
        "60_79": 0,
        "80_100": 0,
    }
