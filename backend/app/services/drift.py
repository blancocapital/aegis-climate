import hashlib
import json
from typing import Dict, List, Optional, Tuple

CLASS_ORDER = {"NEW": 0, "REMOVED": 1, "MODIFIED": 2}
COMPARE_FIELDS = [
    "external_location_id",
    "address_line1",
    "city",
    "state_region",
    "postal_code",
    "country",
    "latitude",
    "longitude",
    "currency",
    "lob",
    "product_code",
    "tiv",
    "limit",
    "premium",
    "quality_tier",
]


def _canonical_json(obj: Dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _snapshot(row: Dict) -> Dict:
    return {field: row.get(field) for field in COMPARE_FIELDS if field in row}


def _stable_sort_key(detail: Dict) -> Tuple:
    return (CLASS_ORDER.get(detail.get("classification"), 99), detail.get("external_location_id", ""))


def compare_exposures(locations_a: List[Dict], locations_b: List[Dict], config: Optional[Dict] = None):
    idx_a = {str(r.get("external_location_id")): r for r in locations_a}
    idx_b = {str(r.get("external_location_id")): r for r in locations_b}
    details: List[Dict] = []
    changed = 0
    new = 0
    removed = 0
    keys = sorted(set(idx_a.keys()) | set(idx_b.keys()))
    for key in keys:
        a = idx_a.get(key)
        b = idx_b.get(key)
        if a and not b:
            removed += 1
            details.append(
                {
                    "external_location_id": key,
                    "classification": "REMOVED",
                    "delta_json": {"before": _snapshot(a)},
                }
            )
        elif b and not a:
            new += 1
            details.append(
                {
                    "external_location_id": key,
                    "classification": "NEW",
                    "delta_json": {"after": _snapshot(b)},
                }
            )
        else:
            changed_fields = []
            before = _snapshot(a)
            after = _snapshot(b)
            deltas = {}
            for field in COMPARE_FIELDS:
                if before.get(field) != after.get(field):
                    changed_fields.append(field)
                    deltas[field] = {"before": before.get(field), "after": after.get(field)}
                    if field in {"tiv", "limit", "premium"}:
                        try:
                            before_val = float(before.get(field)) if before.get(field) is not None else None
                            after_val = float(after.get(field)) if after.get(field) is not None else None
                            if before_val is not None and after_val is not None:
                                deltas[field]["delta"] = after_val - before_val
                        except (TypeError, ValueError):
                            pass
            if changed_fields:
                changed += 1
                details.append(
                    {
                        "external_location_id": key,
                        "classification": "MODIFIED",
                        "delta_json": {"changed_fields": changed_fields, "changes": deltas},
                    }
                )
    details = sorted(details, key=_stable_sort_key)
    summary = {
        "NEW": new,
        "REMOVED": removed,
        "MODIFIED": changed,
        "total": len(details),
    }
    artifact = _canonical_json(details).encode()
    checksum = hashlib.sha256(artifact).hexdigest()
    return summary, details, artifact, checksum
