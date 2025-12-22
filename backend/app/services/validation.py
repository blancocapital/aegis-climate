import csv
import io
import json
import hashlib
from typing import Dict, List, Tuple

SEVERITIES = ["ERROR", "WARN", "INFO"]


def compute_checksum_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_issue_sort(issue: Dict) -> Tuple:
    return (
        issue.get("row_number", 0),
        SEVERITIES.index(issue.get("severity", "ERROR")),
        issue.get("field", ""),
        issue.get("code", ""),
    )


def _as_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def validate_rows(rows: List[Dict], mapping: Dict) -> Tuple[Dict, List[Dict], bytes, str]:
    issues: List[Dict] = []
    summary = {"ERROR": 0, "WARN": 0, "INFO": 0, "total_rows": len(rows)}
    for idx, row in enumerate(rows, start=1):
        mapped = {dst: row.get(src, "") for src, dst in mapping.items()} if mapping else row
        ext_id = (mapped.get("external_location_id") or "").strip()
        if not ext_id:
            issues.append({
                "row_number": idx,
                "severity": "ERROR",
                "field": "external_location_id",
                "code": "MISSING_EXTERNAL_ID",
                "message": "external_location_id is required",
            })
        lat = mapped.get("latitude") or mapped.get("lat")
        lon = mapped.get("longitude") or mapped.get("lon")
        address = mapped.get("address_line1")
        city = mapped.get("city")
        country = mapped.get("country")
        state_region = mapped.get("state_region")
        postal_code = mapped.get("postal_code")
        if not ((lat and lon) or (address and city and state_region and postal_code and country)):
            issues.append({
                "row_number": idx,
                "severity": "ERROR",
                "field": "location",
                "code": "MISSING_LOCATION",
                "message": "Latitude/Longitude or full address fields required",
            })
        tiv = mapped.get("tiv")
        if tiv is None or tiv == "":
            issues.append({
                "row_number": idx,
                "severity": "ERROR",
                "field": "tiv",
                "code": "MISSING_TIV",
                "message": "tiv is required",
            })
        else:
            parsed_tiv = _as_float(tiv)
            if parsed_tiv is None:
                issues.append({
                    "row_number": idx,
                    "severity": "ERROR",
                    "field": "tiv",
                    "code": "INVALID_TIV",
                    "message": "tiv must be numeric",
                })
            elif parsed_tiv < 0:
                issues.append({
                    "row_number": idx,
                    "severity": "ERROR",
                    "field": "tiv",
                    "code": "NEGATIVE_TIV",
                    "message": "tiv must be non-negative",
                })
        currency = (mapped.get("currency") or "").strip()
        if not currency:
            issues.append({
                "row_number": idx,
                "severity": "WARN",
                "field": "currency",
                "code": "MISSING_CURRENCY_DEFAULTED",
                "message": "currency missing; will default to tenant currency",
            })
        lob = (mapped.get("lob") or "").strip()
        product_code = (mapped.get("product_code") or "").strip()
        if not lob and not product_code:
            issues.append({
                "row_number": idx,
                "severity": "ERROR",
                "field": "segmentation",
                "code": "MISSING_SEGMENTATION",
                "message": "lob or product_code required",
            })
        for numeric_field in ["limit", "premium"]:
            val = mapped.get(numeric_field)
            if val is None or val == "":
                continue
            parsed = _as_float(val)
            if parsed is None:
                issues.append({
                    "row_number": idx,
                    "severity": "WARN",
                    "field": numeric_field,
                    "code": f"INVALID_{numeric_field.upper()}",
                    "message": f"{numeric_field} must be numeric",
                })
            elif parsed < 0:
                issues.append({
                    "row_number": idx,
                    "severity": "WARN",
                    "field": numeric_field,
                    "code": f"NEGATIVE_{numeric_field.upper()}",
                    "message": f"{numeric_field} should be non-negative",
                })
    issues = sorted(issues, key=_stable_issue_sort)
    for issue in issues:
        summary[issue["severity"]] += 1
    artifact_bytes = json.dumps(issues, sort_keys=True, separators=(",", ":")).encode()
    checksum = compute_checksum_sha256(artifact_bytes)
    return summary, issues, artifact_bytes, checksum


def read_csv_bytes(raw_bytes: bytes) -> List[Dict]:
    reader = csv.DictReader(io.StringIO(raw_bytes.decode()))
    return list(reader)
