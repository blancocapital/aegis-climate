from typing import Dict, List


def init_peril_coverage(perils: List[str]) -> Dict[str, Dict[str, int]]:
    return {peril: {"with_score": 0, "missing_score": 0} for peril in perils}


def update_peril_coverage(coverage: Dict[str, Dict[str, int]], hazards: Dict, perils: List[str]) -> None:
    for peril in perils:
        entry = hazards.get(peril)
        score = entry.get("score") if isinstance(entry, dict) else None
        if isinstance(score, (int, float)):
            coverage[peril]["with_score"] += 1
        else:
            coverage[peril]["missing_score"] += 1


def compute_bucket_percentages(bucket_counts: Dict[str, int], total: int) -> Dict[str, float]:
    if total <= 0:
        return {key: 0.0 for key in bucket_counts}
    return {key: float(value) / total for key, value in bucket_counts.items()}
