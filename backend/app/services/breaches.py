from typing import Any, Dict, List
import operator
from app.services.rollup import _canonical_json, _hash_key


def evaluate_rule_on_rollup_rows(rows: List[Dict[str, Any]], rule_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    metric = rule_json.get("metric")
    op_symbol = rule_json.get("operator")
    target_value = rule_json.get("value")
    where = rule_json.get("where") or {}
    ops = {
        ">": operator.gt,
        ">=": operator.ge,
        "<": operator.lt,
        "<=": operator.le,
        "==": operator.eq,
        "!=": operator.ne,
    }
    op_fn = ops.get(op_symbol)
    if not op_fn:
        return []

    matches: List[Dict[str, Any]] = []
    for row in rows:
        rollup_key_json = row.get("rollup_key_json") or {}
        metrics_json = row.get("metrics_json") or {}
        valid = True
        for k, v in where.items():
            if rollup_key_json.get(k) != v:
                valid = False
                break
        if not valid:
            continue
        metric_value = metrics_json.get(metric)
        if metric_value is None:
            continue
        try:
            if op_fn(float(metric_value), float(target_value)):
                matches.append(
                    {
                        "rollup_key_json": rollup_key_json,
                        "rollup_key_hash": row.get("rollup_key_hash") or _hash_key(rollup_key_json),
                        "metric_value": float(metric_value),
                    }
                )
        except (TypeError, ValueError):
            continue
    matches.sort(key=lambda m: _canonical_json(m["rollup_key_json"]))
    return matches
