import hashlib
import json
from typing import Any, Dict, List, Optional


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def fingerprint_resilience_scores_request(
    tenant_id: str,
    exposure_version_id: int,
    hazard_version_ids: Optional[List[int]],
    config: Optional[Dict[str, Any]],
    scoring_version: str,
    code_version: Optional[str],
    policy_pack_version_id: Optional[int],
) -> str:
    hazard_version_ids = sorted(hazard_version_ids or [])
    payload = {
        "tenant_id": tenant_id,
        "exposure_version_id": exposure_version_id,
        "hazard_dataset_version_ids": hazard_version_ids,
        "config": config or {},
        "scoring_version": scoring_version,
        "code_version": code_version,
        "policy_pack_version_id": policy_pack_version_id if policy_pack_version_id is not None else "default",
    }
    payload_str = canonical_json(payload)
    return hashlib.sha256(payload_str.encode()).hexdigest()
