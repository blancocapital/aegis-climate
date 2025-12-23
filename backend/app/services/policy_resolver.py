from typing import Any, Dict, Optional, Tuple

from app.models import PolicyPack, PolicyPackVersion, Tenant
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


def _default_policy_meta() -> Dict[str, Any]:
    return {
        "policy_pack_id": None,
        "policy_pack_version_id": None,
        "version_label": "default",
        "policy_pack_name": "default",
    }


def _resolve_policy_pack_version_id(db, tenant_id: str, policy_pack_version_id: Optional[int]) -> Optional[int]:
    if policy_pack_version_id is not None or db is None:
        return policy_pack_version_id
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        return None
    return tenant.default_policy_pack_version_id


def resolve_policy_version(
    db,
    tenant_id: str,
    policy_pack_version_id: Optional[int],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    resolved_version_id = _resolve_policy_pack_version_id(db, tenant_id, policy_pack_version_id)
    if resolved_version_id is None:
        return (dict(DEFAULT_CONFIG), dict(DEFAULT_POLICY), _default_policy_meta())
    if db is None:
        raise ValueError("Database session required for policy resolution")
    version = db.get(PolicyPackVersion, resolved_version_id)
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
        "policy_pack_name": pack.name,
    }
    return scoring_config, underwriting_policy, meta
