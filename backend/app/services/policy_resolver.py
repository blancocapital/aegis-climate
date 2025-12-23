from typing import Any, Dict, Optional, Tuple

from app.models import PolicyPack, PolicyPackVersion
from app.services.resilience import DEFAULT_CONFIG
from app.services.underwriting_decision import DEFAULT_POLICY


def merge_policy_overrides(base: Dict[str, Any], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(base or {})
    if not override:
        return merged
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_policy_overrides(merged[key], value)
        else:
            merged[key] = value
    return merged


def resolve_policy_version(
    db,
    tenant_id: str,
    policy_pack_version_id: Optional[int],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    if policy_pack_version_id is None:
        return (
            dict(DEFAULT_CONFIG),
            dict(DEFAULT_POLICY),
            {
                "policy_pack_id": None,
                "policy_pack_version_id": None,
                "version_label": "default",
                "name": "default",
            },
        )
    if db is None:
        raise ValueError("Database session required for policy resolution")
    version = db.get(PolicyPackVersion, policy_pack_version_id)
    if not version or version.tenant_id != tenant_id:
        raise ValueError("Policy pack version not found")
    pack = db.get(PolicyPack, version.policy_pack_id)
    if not pack or pack.tenant_id != tenant_id:
        raise ValueError("Policy pack not found")
    scoring_config = merge_policy_overrides(dict(DEFAULT_CONFIG), version.scoring_config_json or {})
    underwriting_policy = merge_policy_overrides(dict(DEFAULT_POLICY), version.underwriting_policy_json or {})
    meta = {
        "policy_pack_id": pack.id,
        "policy_pack_version_id": version.id,
        "version_label": version.version_label,
        "name": pack.name,
    }
    return scoring_config, underwriting_policy, meta
