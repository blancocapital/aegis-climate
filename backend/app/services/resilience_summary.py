from typing import Dict, List


def bucket_counts(scores: List[int]) -> Dict[str, int]:
    buckets = {
        "0_19": 0,
        "20_39": 0,
        "40_59": 0,
        "60_79": 0,
        "80_100": 0,
    }
    for score in scores:
        if score <= 19:
            buckets["0_19"] += 1
        elif score <= 39:
            buckets["20_39"] += 1
        elif score <= 59:
            buckets["40_59"] += 1
        elif score <= 79:
            buckets["60_79"] += 1
        else:
            buckets["80_100"] += 1
    return buckets
