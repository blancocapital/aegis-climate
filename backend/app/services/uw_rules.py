import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.services.hazard_query import coerce_float


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _sorted_unique(values: Iterable[Any]) -> List[Any]:
    items = [v for v in values if v is not None]
    return sorted(set(items), key=lambda v: str(v))


def _get_field_value(record: Dict[str, Any], field: str) -> Any:
    if "." not in field:
        return record.get(field)
    value: Any = record
    for part in field.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _compare_scalar(actual: Any, op: str, expected: Any) -> bool:
    if op in ("==", "!="):
        return actual == expected if op == "==" else actual != expected
    if op in ("in", "not_in"):
        expected_list = _as_list(expected)
        contains = actual in expected_list
        return contains if op == "in" else not contains
    if op in (">", ">=", "<", "<="):
        actual_num = coerce_float(actual)
        expected_num = coerce_float(expected)
        if actual_num is None or expected_num is None:
            return False
        if op == ">":
            return actual_num > expected_num
        if op == ">=":
            return actual_num >= expected_num
        if op == "<":
            return actual_num < expected_num
        if op == "<=":
            return actual_num <= expected_num
    return False


def evaluate_predicate(predicate: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
    field = predicate.get("field", "")
    op = predicate.get("op", "")
    expected = predicate.get("value")
    actual = _get_field_value(record, field)
    matched = False

    if op == "exists":
        if isinstance(actual, list):
            matched = len(actual) > 0
        else:
            matched = actual is not None and actual != ""
    elif isinstance(actual, list):
        actual_list = _sorted_unique(actual)
        expected_list = _as_list(expected)
        if op == "in":
            matched = any(item in expected_list for item in actual_list)
        elif op == "not_in":
            matched = all(item not in expected_list for item in actual_list)
        elif op == "==":
            matched = any(item == expected for item in actual_list) if not isinstance(expected, list) else any(
                item in expected for item in actual_list
            )
        elif op == "!=":
            matched = all(item != expected for item in actual_list) if not isinstance(expected, list) else all(
                item not in expected for item in actual_list
            )
    else:
        matched = _compare_scalar(actual, op, expected)

    if isinstance(actual, list):
        actual = _sorted_unique(actual)
    return {
        "field": field,
        "op": op,
        "expected": expected,
        "actual": actual,
        "matched": matched,
    }


def evaluate_rule(rule_json: Dict[str, Any], record: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    when = rule_json.get("when") or {}
    predicates: List[Dict[str, Any]] = []
    logic = "all" if "all" in when else "any" if "any" in when else "none"
    clauses = when.get("all") if "all" in when else when.get("any") if "any" in when else []
    for predicate in clauses or []:
        predicates.append(evaluate_predicate(predicate, record))

    if logic == "all":
        matched = all(p["matched"] for p in predicates) if predicates else False
    elif logic == "any":
        matched = any(p["matched"] for p in predicates) if predicates else False
    else:
        matched = False

    explanation = {
        "logic": logic,
        "predicates": predicates,
        "observed": _observed_values(predicates),
    }
    return matched, explanation


def _observed_values(predicates: List[Dict[str, Any]]) -> Dict[str, Any]:
    observed: Dict[str, Any] = {}
    for predicate in predicates:
        field = predicate.get("field")
        if not field or field in observed:
            continue
        observed[field] = predicate.get("actual")
    return observed


def build_location_record(location: Any, hazard_entries: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    hazard_entries = hazard_entries or []
    hazard_bands = _sorted_unique(entry.get("band") for entry in hazard_entries)
    hazard_categories = _sorted_unique(entry.get("hazard_category") for entry in hazard_entries)
    return {
        "location_id": getattr(location, "id", None),
        "external_location_id": getattr(location, "external_location_id", None),
        "tiv": getattr(location, "tiv", None),
        "country": getattr(location, "country", None),
        "state_region": getattr(location, "state_region", None),
        "postal_code": getattr(location, "postal_code", None),
        "lob": getattr(location, "lob", None),
        "product_code": getattr(location, "product_code", None),
        "currency": getattr(location, "currency", None),
        "quality_tier": getattr(location, "quality_tier", None),
        "geocode_confidence": getattr(location, "geocode_confidence", None),
        "hazard_band": hazard_bands,
        "hazard_category": hazard_categories,
    }


def build_rollup_record(rollup_key_json: Dict[str, Any], metrics_json: Dict[str, Any]) -> Dict[str, Any]:
    return {
        **(rollup_key_json or {}),
        "rollup": {"metrics": metrics_json or {}},
    }


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
