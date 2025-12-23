from typing import Dict, List


def score_bucket(score: int) -> str:
    if score <= 19:
        return "0_19"
    if score <= 39:
        return "20_39"
    if score <= 59:
        return "40_59"
    if score <= 79:
        return "60_79"
    return "80_100"


def bucket_keys() -> List[str]:
    return ["0_19", "20_39", "40_59", "60_79", "80_100"]


def empty_bucket_dict() -> Dict[str, int]:
    return {key: 0 for key in bucket_keys()}
