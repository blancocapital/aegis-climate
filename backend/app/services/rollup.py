import hashlib
import json
from typing import Dict, List, Tuple, Any, Optional


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _hash_key(obj: Any) -> str:
    return hashlib.sha256(_canonical_json(obj).encode()).hexdigest()


def compute_rollup(
    enriched_records: List[Dict[str, Any]],
    dimensions: List[str],
    measures: List[Dict[str, str]],
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    filters = filters or {}

    def record_passes(rec: Dict[str, Any]) -> bool:
        for key, expected in filters.items():
            val = rec.get(key)
            if isinstance(expected, list):
                if val not in expected:
                    return False
            else:
                if val != expected:
                    return False
        return True

    grouped: Dict[Tuple, Dict[str, Any]] = {}
    for rec in enriched_records:
        if not record_passes(rec):
            continue
        key_values = tuple(rec.get(dim) for dim in dimensions)
        if key_values not in grouped:
            grouped[key_values] = {"rollup_key_json": {dim: rec.get(dim) for dim in dimensions}, "metrics": {}}
        metrics_bucket = grouped[key_values]["metrics"]
        for measure in measures:
            name = measure.get("name")
            op = measure.get("op")
            field = measure.get("field")
            if op == "count":
                metrics_bucket[name] = metrics_bucket.get(name, 0) + 1
            elif op == "sum":
                try:
                    value = float(rec.get(field)) if rec.get(field) is not None else 0.0
                except (TypeError, ValueError):
                    value = 0.0
                metrics_bucket[name] = metrics_bucket.get(name, 0.0) + value

    rows: List[Dict[str, Any]] = []
    for bucket in grouped.values():
        rollup_key_json = bucket["rollup_key_json"]
        rollup_key_hash = _hash_key(rollup_key_json)
        rows.append(
            {
                "rollup_key_json": rollup_key_json,
                "rollup_key_hash": rollup_key_hash,
                "metrics_json": bucket["metrics"],
            }
        )
    rows.sort(key=lambda r: _canonical_json(r["rollup_key_json"]))
    checksum = _hash_key([{ "rollup_key_json": r["rollup_key_json"], "metrics_json": r["metrics_json"]} for r in rows])
    return rows, checksum
