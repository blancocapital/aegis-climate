from typing import Any, Dict, Optional


def resolve_keyset_pagination(
    limit: int,
    offset: int,
    after_id: Optional[int],
    max_limit: int = 500,
) -> Dict[str, Any]:
    normalized_limit = min(max(limit, 1), max_limit)
    normalized_offset = max(offset, 0)
    if after_id is not None:
        return {
            "limit": normalized_limit,
            "offset": None,
            "after_id": max(after_id, 0),
        }
    return {
        "limit": normalized_limit,
        "offset": normalized_offset,
        "after_id": None,
    }
