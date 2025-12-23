from app.services.request_fingerprint import fingerprint_resilience_scores_request


def test_fingerprint_deterministic():
    first = fingerprint_resilience_scores_request(
        tenant_id="tenant",
        exposure_version_id=1,
        hazard_version_ids=[3, 2],
        config={"b": 2, "a": 1},
        scoring_version="v1",
        code_version="dev",
        policy_pack_version_id=None,
    )
    second = fingerprint_resilience_scores_request(
        tenant_id="tenant",
        exposure_version_id=1,
        hazard_version_ids=[3, 2],
        config={"a": 1, "b": 2},
        scoring_version="v1",
        code_version="dev",
        policy_pack_version_id=None,
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
        policy_pack_version_id=None,
    )
    second = fingerprint_resilience_scores_request(
        tenant_id="tenant",
        exposure_version_id=1,
        hazard_version_ids=[3, 10, 2],
        config=None,
        scoring_version="v1",
        code_version=None,
        policy_pack_version_id=None,
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
        policy_pack_version_id=5,
    )
    second = fingerprint_resilience_scores_request(
        tenant_id="tenant",
        exposure_version_id=1,
        hazard_version_ids=[1],
        config={"nested": {"a": 1, "b": 2}},
        scoring_version="v1",
        code_version="dev",
        policy_pack_version_id=5,
    )
    assert first == second


def test_fingerprint_changes_with_policy_version():
    base = fingerprint_resilience_scores_request(
        tenant_id="tenant",
        exposure_version_id=1,
        hazard_version_ids=[1],
        config=None,
        scoring_version="v1",
        code_version="dev",
        policy_pack_version_id=1,
    )
    changed = fingerprint_resilience_scores_request(
        tenant_id="tenant",
        exposure_version_id=1,
        hazard_version_ids=[1],
        config=None,
        scoring_version="v1",
        code_version="dev",
        policy_pack_version_id=2,
    )
    assert base != changed
