import csv
import io
import json
from typing import Any, Dict, Iterator, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Location, ResilienceScoreItem, ResilienceScoreResult

CSV_COLUMNS = [
    "location_id",
    "external_location_id",
    "latitude",
    "longitude",
    "address_line1",
    "city",
    "state_region",
    "postal_code",
    "country",
    "lob",
    "tiv",
    "resilience_score",
    "risk_score",
    "warnings",
    "hazards_json",
    "structural_json",
    "input_structural_json",
    "policy_pack_version_id",
    "policy_used_json",
    "policy_version_label",
]


def _serialize_json(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _serialize_warnings(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, list):
        return ";".join([str(v) for v in value])
    return str(value)


def serialize_export_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "location_id": row.get("location_id"),
        "external_location_id": row.get("external_location_id"),
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "address_line1": row.get("address_line1"),
        "city": row.get("city"),
        "state_region": row.get("state_region"),
        "postal_code": row.get("postal_code"),
        "country": row.get("country"),
        "lob": row.get("lob"),
        "tiv": row.get("tiv"),
        "resilience_score": row.get("resilience_score"),
        "risk_score": row.get("risk_score"),
        "warnings": _serialize_warnings(row.get("warnings")),
        "hazards_json": _serialize_json(row.get("hazards_json")),
        "structural_json": _serialize_json(row.get("structural_json")),
        "input_structural_json": _serialize_json(row.get("input_structural_json")),
        "policy_pack_version_id": row.get("policy_pack_version_id"),
        "policy_used_json": _serialize_json(row.get("policy_used_json")),
        "policy_version_label": row.get("policy_version_label") or "",
    }


def rows_to_csv(rows: List[Dict[str, Any]], include_header: bool = True) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n")
    if include_header:
        writer.writeheader()
    for row in rows:
        writer.writerow(serialize_export_row(row))
    return buffer.getvalue()


def iter_resilience_export_rows(
    db: Session,
    tenant_id: str,
    result_id: int,
    batch_size: int = 2000,
) -> Iterator[str]:
    start_after_id = 0
    first = True
    while True:
        rows = db.execute(
            select(ResilienceScoreItem, Location, ResilienceScoreResult)
            .join(Location, ResilienceScoreItem.location_id == Location.id)
            .join(ResilienceScoreResult, ResilienceScoreItem.resilience_score_result_id == ResilienceScoreResult.id)
            .where(
                ResilienceScoreItem.tenant_id == tenant_id,
                ResilienceScoreItem.resilience_score_result_id == result_id,
                ResilienceScoreItem.id > start_after_id,
            )
            .order_by(ResilienceScoreItem.id.asc())
            .limit(batch_size)
        ).all()
        if not rows:
            break
        export_rows: List[Dict[str, Any]] = []
        for item, location, result in rows:
            warnings = []
            input_structural = None
            policy_version_label = None
            if isinstance(result.policy_used_json, dict):
                policy_version_label = result.policy_used_json.get("version_label")
            if isinstance(item.result_json, dict):
                warnings = item.result_json.get("warnings") or []
                input_structural = item.result_json.get("input_structural")
            export_rows.append(
                {
                    "location_id": item.location_id,
                    "external_location_id": location.external_location_id,
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "address_line1": location.address_line1,
                    "city": location.city,
                    "state_region": location.state_region,
                    "postal_code": location.postal_code,
                    "country": location.country,
                    "lob": location.lob,
                    "tiv": location.tiv,
                    "resilience_score": item.resilience_score,
                    "risk_score": item.risk_score,
                    "warnings": warnings,
                    "hazards_json": item.hazards_json,
                    "structural_json": location.structural_json,
                    "input_structural_json": input_structural,
                    "policy_pack_version_id": result.policy_pack_version_id,
                    "policy_used_json": result.policy_used_json,
                    "policy_version_label": policy_version_label or "default",
                }
            )
            start_after_id = item.id
        yield rows_to_csv(export_rows, include_header=first)
        first = False
