from typing import Any, Dict, Optional


def merge_run_progress(
    existing: Optional[Dict[str, Any]],
    processed: Optional[int],
    total: Optional[int],
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    merged = dict(existing or {})
    if processed is not None:
        merged["processed"] = int(processed)
    if total is not None:
        merged["total"] = int(total)
    if extra:
        for key, value in extra.items():
            merged[key] = value
    return merged
