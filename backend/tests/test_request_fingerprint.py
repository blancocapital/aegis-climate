from app.services.request_fingerprint import fingerprint_resilience_scores_request


def test_fingerprint_deterministic():
    first = fingerprint_resilience_scores_request(
        tenant_id="tenant",
        exposure_version_id=1,
        hazard_version_ids=[3, 2],
        config={"b": 2, "a": 1},
        scoring_version="v1",
        code_version="dev",
    )
    second = fingerprint_resilience_scores_request(
        tenant_id="tenant",
        exposure_version_id=1,
        hazard_version_ids=[3, 2],
        config={"a": 1, "b": 2},
        scoring_version="v1",
        code_version="dev",
    )
    assert first == second


def test_fingerprint_sorts_hazard_versions():
    first = fingerprint_resilience_scores_request(
        tenant_id="tenant",
        exposure_version_id=1,
        hazard_version_ids=[10, 2, 3],
        config=None,
        scoring_version="v1",
        code_version=None,
    )
    second = fingerprint_resilience_scores_request(
        tenant_id="tenant",
        exposure_version_id=1,
        hazard_version_ids=[3, 10, 2],
        config=None,
        scoring_version="v1",
        code_version=None,
    )
    assert first == second


def test_fingerprint_config_order_insensitive():
    first = fingerprint_resilience_scores_request(
        tenant_id="tenant",
        exposure_version_id=1,
        hazard_version_ids=[1],
        config={"nested": {"b": 2, "a": 1}},
        scoring_version="v1",
        code_version="dev",
    )
    second = fingerprint_resilience_scores_request(
        tenant_id="tenant",
        exposure_version_id=1,
        hazard_version_ids=[1],
        config={"nested": {"a": 1, "b": 2}},
        scoring_version="v1",
        code_version="dev",
    )
    assert first == second
