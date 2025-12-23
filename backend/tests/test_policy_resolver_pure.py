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
    assert meta["policy_pack_name"] == "default"


def test_resolve_policy_uses_tenant_default():
    class FakeTenant:
        def __init__(self, default_policy_pack_version_id):
            self.default_policy_pack_version_id = default_policy_pack_version_id

    class FakeVersion:
        def __init__(self):
            self.id = 7
            self.tenant_id = "tenant"
            self.policy_pack_id = 3
            self.version_label = "v2"
            self.scoring_config_json = {"unknown_hazard_score": 0.2}
            self.underwriting_policy_json = {"score_accept_min": 80}

    class FakePack:
        def __init__(self):
            self.id = 3
            self.tenant_id = "tenant"
            self.name = "QA Pack"

    class FakeDB:
        def __init__(self):
            self.tenant = FakeTenant(7)
            self.version = FakeVersion()
            self.pack = FakePack()

        def get(self, model, key):
            if model.__name__ == "Tenant":
                return self.tenant
            if model.__name__ == "PolicyPackVersion":
                return self.version if key == 7 else None
            if model.__name__ == "PolicyPack":
                return self.pack if key == 3 else None
            return None

    scoring_config, underwriting_policy, meta = resolve_policy_version(FakeDB(), "tenant", None)
    assert scoring_config["unknown_hazard_score"] == 0.2
    assert underwriting_policy["score_accept_min"] == 80
    assert meta["policy_pack_version_id"] == 7
    assert meta["policy_pack_name"] == "QA Pack"
