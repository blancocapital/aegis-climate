from app.services.policy_resolver import merge_policy_overrides, resolve_policy_version
from app.services.resilience import DEFAULT_CONFIG
from app.services.underwriting_decision import DEFAULT_POLICY


def test_merge_policy_overrides_deterministic():
    base = {"weights": {"flood": 0.3, "wind": 0.1}, "unknown_hazard_score": 0.5}
    override = {"weights": {"flood": 0.4}, "extra": {"a": 1}}
    merged = merge_policy_overrides(base, override)
    assert merged["weights"]["flood"] == 0.4
    assert merged["weights"]["wind"] == 0.1
    assert merged["unknown_hazard_score"] == 0.5
    assert merged["extra"]["a"] == 1


def test_resolve_policy_default_without_db():
    scoring_config, underwriting_policy, meta = resolve_policy_version(None, "tenant", None)
    assert scoring_config["weights"] == DEFAULT_CONFIG["weights"]
    assert underwriting_policy["score_accept_min"] == DEFAULT_POLICY["score_accept_min"]
    assert meta["version_label"] == "default"
