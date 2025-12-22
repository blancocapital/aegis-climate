from typing import Dict, List


def quality_scores(location: Dict) -> Dict:
    completeness = 100
    reasons: List[str] = []
    if not location.get("address_line1"):
        completeness -= 20
        reasons.append("MISSING_ADDRESS")
    if location.get("tiv") in (None, ""):
        completeness -= 30
        reasons.append("MISSING_TIV")
    geocode_conf = location.get("geocode_confidence") or 0
    geocode_score = int(geocode_conf * 100)
    financial_sanity = 100 if (location.get("tiv") is not None and (location.get("tiv") or 0) >= 0) else 60
    overall = int((completeness + geocode_score + financial_sanity) / 3)
    tier = "C"
    if overall >= 85 and geocode_score >= 80:
        tier = "A"
    elif overall >= 70 and geocode_score >= 60:
        tier = "B"
    if geocode_conf < 0.6:
        reasons.append("LOW_GEOCODE_CONFIDENCE")
    return {
        "completeness_score": completeness,
        "geocode_score": geocode_score,
        "financial_sanity_score": financial_sanity,
        "overall_score": overall,
        "quality_tier": tier,
        "reasons": reasons,
    }
