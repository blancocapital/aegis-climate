from app.services.bucketing import bucket_keys, score_bucket


def test_bucket_boundaries():
    cases = {
        19: "0_19",
        20: "20_39",
        39: "20_39",
        40: "40_59",
        59: "40_59",
        60: "60_79",
        79: "60_79",
        80: "80_100",
        100: "80_100",
    }
    for score, expected in cases.items():
        assert score_bucket(score) == expected


def test_bucket_keys_order():
    assert bucket_keys() == ["0_19", "20_39", "40_59", "60_79", "80_100"]
