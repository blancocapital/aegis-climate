import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from celery import Celery
from sqlalchemy import select

from app.core.config import get_settings
from app.db import SessionLocal
from sqlalchemy import func
from app.models import (
    Breach,
    DriftDetail,
    DriftRun,
    ExposureUpload,
    ExposureVersion,
    HazardDataset,
    HazardDatasetVersion,
    HazardFeaturePolygon,
    HazardOverlayResult,
    Location,
    LocationHazardAttribute,
    ResilienceScoreItem,
    ResilienceScoreResult,
    PropertyProfile,
    AuditEvent,
    MappingTemplate,
    RollupConfig,
    RollupResult,
    RollupResultItem,
    Run,
    RunStatus,
    RunType,
    Tenant,
    ThresholdRule,
    UWRule,
    UWFinding,
    ValidationResult,
)
from app.services.validation import read_csv_bytes, validate_rows
from app.services.commit import canonicalize_rows, to_location_dict
from app.services.geocode import geocode_address
from app.services.hazard_query import extract_hazard_entry, merge_worst_in_peril
from app.services.quality import quality_scores
from app.services.quality_metrics import init_peril_coverage, update_peril_coverage
from app.services.resilience import DEFAULT_WEIGHTS, compute_resilience_score
from app.services.property_enrichment import (
    STRUCTURAL_KEYS,
    address_fingerprint,
    is_profile_fresh,
    normalize_address,
    run_enrichment_pipeline,
)
from app.services.structural import merge_structural, normalize_structural
from app.services.rollup import compute_rollup
from app.services.breaches import evaluate_rule_on_rollup_rows
from app.services.drift import COMPARE_FIELDS, compare_exposures
from app.services.run_progress import merge_run_progress
from app.services.uw_rules import (
    build_location_record,
    build_rollup_record,
    canonical_json,
    evaluate_rule,
)
from app.storage.s3 import compute_checksum, get_object, put_object

settings = get_settings()
logger = logging.getLogger(__name__)

celery_app = Celery(
    "aegis", broker=settings.redis_url, backend=settings.redis_url
)


def _attach_request_id(run: Run, request_id: Optional[str]) -> None:
    if request_id and not run.request_id:
        run.request_id = request_id


def _update_progress(
    session: SessionLocal,
    run: Run,
    processed: Optional[int],
    total: Optional[int],
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    run.output_refs_json = merge_run_progress(run.output_refs_json, processed, total, extra=extra)
    session.commit()


def _log_task_start(task_name: str, run_id: int, request_id: Optional[str]) -> None:
    logger.info("%s started run_id=%s request_id=%s", task_name, run_id, request_id)


def _uw_rule_disposition(rule_json: Dict[str, Any]) -> str:
    return ((rule_json or {}).get("then") or {}).get("disposition") or "NONE"


def _uw_rule_conditions(rule_json: Dict[str, Any]) -> List[str]:
    return ((rule_json or {}).get("then") or {}).get("suggested_conditions") or []


def _build_uw_explanation(rule: UWRule, record: Dict[str, Any], eval_explanation: Dict[str, Any]) -> Dict[str, Any]:
    context_fields = [
        "tiv",
        "country",
        "state_region",
        "postal_code",
        "lob",
        "product_code",
        "currency",
        "quality_tier",
        "geocode_confidence",
        "hazard_band",
        "hazard_category",
    ]
    context = {field: record.get(field) for field in context_fields if field in record}
    if "rollup" in record:
        context["rollup"] = record.get("rollup")
    return {
        "rule_id": rule.id,
        "rule_name": rule.name,
        "category": rule.category,
        "severity": rule.severity,
        "target": rule.target,
        "disposition": _uw_rule_disposition(rule.rule_json),
        "suggested_conditions": _uw_rule_conditions(rule.rule_json),
        "evaluation": eval_explanation,
        "observed": eval_explanation.get("observed") or {},
        "context": context,
    }


@celery_app.task
def validate_upload(run_id: int, upload_id: str, tenant_id: str, request_id: Optional[str] = None):
    session = SessionLocal()
    run = session.get(Run, run_id)
    if not run or run.tenant_id != tenant_id:
        return
    try:
        if run.status == RunStatus.CANCELLED:
            return
        _attach_request_id(run, request_id)
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
        _log_task_start("validate_upload", run_id, request_id)
        upload = session.get(ExposureUpload, upload_id)
        if not upload:
            raise ValueError("upload not found")
        mapping = session.get(MappingTemplate, upload.mapping_template_id) if upload.mapping_template_id else None
        key = upload.object_uri.split(f"s3://{settings.minio_bucket}/", 1)[1]
        raw_bytes = get_object(key)
        rows = read_csv_bytes(raw_bytes)
        total_rows = len(rows) if hasattr(rows, "__len__") else None
        _update_progress(session, run, processed=0, total=total_rows)
        summary, issues, artifact_bytes, checksum = validate_rows(rows, mapping.template_json if mapping else {})
        key_errs = f"validations/{tenant_id}/{upload_id}/row_errors.json"
        uri = put_object(key_errs, artifact_bytes, content_type="application/json")
        validation = ValidationResult(
            tenant_id=tenant_id,
            upload_id=upload_id,
            mapping_template_id=upload.mapping_template_id,
            summary_json=summary,
            row_errors_uri=uri,
            checksum=checksum,
        )
        session.add(validation)
        session.commit()
        run.status = RunStatus.SUCCEEDED
        run.completed_at = datetime.utcnow()
        run.output_refs_json = merge_run_progress(
            {"validation_result_id": validation.id},
            processed=total_rows,
            total=total_rows,
        )
        run.artifact_checksums_json = {"row_errors": checksum}
        run.code_version = settings.code_version
        session.commit()
        return {"validation_result_id": validation.id, "run_id": run.id}
    except Exception:
        run.status = RunStatus.FAILED
        run.completed_at = datetime.utcnow()
        session.commit()
        raise
    finally:
        session.close()


@celery_app.task
def rollup_execute(
    run_id: int,
    rollup_result_id: int,
    exposure_version_id: int,
    rollup_config_id: int,
    hazard_overlay_result_ids: List[int],
    tenant_id: str,
    request_id: Optional[str] = None,
):
    session = SessionLocal()
    run = session.get(Run, run_id)
    rollup_result = session.get(RollupResult, rollup_result_id)
    if not run or not rollup_result or run.tenant_id != tenant_id or rollup_result.tenant_id != tenant_id:
        return
    try:
        if run.status == RunStatus.CANCELLED:
            return
        _attach_request_id(run, request_id)
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
        _log_task_start("rollup_execute", run_id, request_id)
        config = session.get(RollupConfig, rollup_config_id)
        if not config or config.tenant_id != tenant_id:
            raise ValueError("rollup config not found")
        exposure_version = session.get(ExposureVersion, exposure_version_id)
        if not exposure_version or exposure_version.tenant_id != tenant_id:
            raise ValueError("exposure version not found")

        overlay_ids = hazard_overlay_result_ids or []
        first_overlay_id = overlay_ids[0] if overlay_ids else None
        attr_map = {}
        if first_overlay_id:
            attrs = session.query(LocationHazardAttribute).filter(
                LocationHazardAttribute.tenant_id == tenant_id,
                LocationHazardAttribute.hazard_overlay_result_id == first_overlay_id,
            ).all()
            attr_map = {a.location_id: a.attributes_json or {} for a in attrs}

        locations = session.query(Location).filter(
            Location.tenant_id == tenant_id,
            Location.exposure_version_id == exposure_version_id,
        ).all()
        total_locations = len(locations)
        _update_progress(session, run, processed=0, total=total_locations)
        enriched = []
        for loc in locations:
            attrs = attr_map.get(loc.id, {})
            enriched.append(
                {
                    "external_location_id": loc.external_location_id,
                    "country": loc.country,
                    "state_region": loc.state_region,
                    "postal_code": loc.postal_code,
                    "lob": loc.lob,
                    "product_code": loc.product_code,
                    "quality_tier": loc.quality_tier,
                    "hazard_band": attrs.get("band"),
                    "hazard_category": attrs.get("hazard_category"),
                    "tiv": loc.tiv,
                    "limit": loc.limit,
                    "premium": loc.premium,
                }
            )

        rows, checksum = compute_rollup(enriched, config.dimensions_json, config.measures_json, config.filters_json)
        result_items = []
        for row in rows:
            result_items.append(
                RollupResultItem(
                    tenant_id=tenant_id,
                    rollup_result_id=rollup_result_id,
                    rollup_key_json=row["rollup_key_json"],
                    rollup_key_hash=row["rollup_key_hash"],
                    metrics_json=row["metrics_json"],
                )
            )
        if result_items:
            session.bulk_save_objects(result_items)
        rollup_result.checksum = checksum
        rollup_result.hazard_overlay_result_ids_json = overlay_ids
        session.commit()
        run.status = RunStatus.SUCCEEDED
        run.completed_at = datetime.utcnow()
        run.output_refs_json = merge_run_progress(
            {"rollup_result_id": rollup_result_id},
            processed=total_locations,
            total=total_locations,
        )
        run.artifact_checksums_json = {"rollup_result_checksum": checksum}
        run.code_version = settings.code_version
        session.commit()
    except Exception:
        run.status = RunStatus.FAILED
        run.completed_at = datetime.utcnow()
        session.commit()
        raise
    finally:
        session.close()


@celery_app.task
def breach_evaluate(
    run_id: int,
    rollup_result_id: int,
    threshold_rule_ids: List[int] | None,
    tenant_id: str,
    request_id: Optional[str] = None,
):
    session = SessionLocal()
    run = session.get(Run, run_id)
    rollup_result = session.get(RollupResult, rollup_result_id)
    if not run or not rollup_result or run.tenant_id != tenant_id or rollup_result.tenant_id != tenant_id:
        return
    try:
        if run.status == RunStatus.CANCELLED:
            return
        _attach_request_id(run, request_id)
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
        _log_task_start("breach_evaluate", run_id, request_id)
        exposure_version = session.get(ExposureVersion, rollup_result.exposure_version_id)
        if not exposure_version or exposure_version.tenant_id != tenant_id:
            raise ValueError("exposure version not found")
        query = select(ThresholdRule).where(ThresholdRule.tenant_id == tenant_id)
        if threshold_rule_ids:
            query = query.where(ThresholdRule.id.in_(threshold_rule_ids))
        rules = session.execute(query).scalars().all()
        rules = [r for r in rules if r.active]

        items = session.query(RollupResultItem).filter(
            RollupResultItem.tenant_id == tenant_id,
            RollupResultItem.rollup_result_id == rollup_result_id,
        ).all()
        _update_progress(session, run, processed=0, total=len(items))
        rows = [
            {
                "rollup_key_json": item.rollup_key_json,
                "rollup_key_hash": item.rollup_key_hash,
                "metrics_json": item.metrics_json,
            }
            for item in items
        ]
        now = datetime.utcnow()
        opened = 0
        resolved = 0
        for rule in rules:
            matches = evaluate_rule_on_rollup_rows(rows, rule.rule_json)
            matched_hashes = set(m["rollup_key_hash"] for m in matches)
            for match in matches:
                breach = session.execute(
                    select(Breach).where(
                        Breach.tenant_id == tenant_id,
                        Breach.threshold_rule_id == rule.id,
                        Breach.exposure_version_id == exposure_version.id,
                        Breach.rollup_key_hash == match["rollup_key_hash"],
                    )
                ).scalar_one_or_none()
                if not breach:
                    breach = Breach(
                        tenant_id=tenant_id,
                        exposure_version_id=exposure_version.id,
                        rollup_result_id=rollup_result_id,
                        threshold_rule_id=rule.id,
                        rollup_key_json=match["rollup_key_json"],
                        rollup_key_hash=match["rollup_key_hash"],
                        metric_name=rule.rule_json.get("metric"),
                        metric_value=match["metric_value"],
                        threshold_value=rule.rule_json.get("value"),
                        status="OPEN",
                        first_seen_at=now,
                        last_seen_at=now,
                        resolved_at=None,
                        last_eval_run_id=run_id,
                    )
                    session.add(breach)
                    opened += 1
                else:
                    breach.metric_value = match["metric_value"]
                    breach.threshold_value = rule.rule_json.get("value")
                    breach.last_seen_at = now
                    breach.rollup_result_id = rollup_result_id
                    breach.last_eval_run_id = run_id
                    if breach.status == "RESOLVED":
                        breach.status = "OPEN"
                        breach.resolved_at = None
                        opened += 1
                session.commit()
            stale_conditions = [
                Breach.tenant_id == tenant_id,
                Breach.threshold_rule_id == rule.id,
                Breach.exposure_version_id == exposure_version.id,
            ]
            if matched_hashes:
                stale_conditions.append(~Breach.rollup_key_hash.in_(matched_hashes))
            stale_breaches = session.execute(select(Breach).where(*stale_conditions)).scalars().all()
            for breach in stale_breaches:
                if breach.status in ("OPEN", "ACKED"):
                    breach.status = "RESOLVED"
                    breach.resolved_at = now
                    breach.last_eval_run_id = run_id
                    breach.last_seen_at = now
                    breach.rollup_result_id = rollup_result_id
                    resolved += 1
            session.commit()
        run.status = RunStatus.SUCCEEDED
        run.completed_at = datetime.utcnow()
        run.output_refs_json = merge_run_progress(
            {
                "rollup_result_id": rollup_result_id,
                "breaches_open": opened,
                "breaches_resolved": resolved,
                "rules_evaluated": len(rules),
            },
            processed=len(items),
            total=len(items),
        )
        run.code_version = settings.code_version
        session.commit()
    except Exception:
        run.status = RunStatus.FAILED
        run.completed_at = datetime.utcnow()
        session.commit()
        raise
    finally:
        session.close()


@celery_app.task
def uw_evaluate(
    run_id: int,
    exposure_version_id: int,
    rollup_result_id: Optional[int],
    uw_rule_ids: Optional[List[int]],
    tenant_id: str,
    request_id: Optional[str] = None,
):
    session = SessionLocal()
    run = session.get(Run, run_id)
    if not run or run.tenant_id != tenant_id:
        return
    try:
        if run.status == RunStatus.CANCELLED:
            return
        _attach_request_id(run, request_id)
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
        _log_task_start("uw_evaluate", run_id, request_id)
        exposure_version = session.get(ExposureVersion, exposure_version_id)
        if not exposure_version or exposure_version.tenant_id != tenant_id:
            raise ValueError("exposure version not found")

        rule_query = select(UWRule).where(UWRule.tenant_id == tenant_id, UWRule.active.is_(True))
        if uw_rule_ids:
            rule_query = rule_query.where(UWRule.id.in_(uw_rule_ids))
        rules = session.execute(rule_query).scalars().all()
        location_rules = [r for r in rules if r.target == "LOCATION"]
        rollup_rules = [r for r in rules if r.target == "ROLLUP"]

        locations = session.query(Location).filter(
            Location.tenant_id == tenant_id,
            Location.exposure_version_id == exposure_version_id,
        ).all()

        hazard_rows = session.execute(
            select(LocationHazardAttribute.location_id, LocationHazardAttribute.attributes_json)
            .join(Location, Location.id == LocationHazardAttribute.location_id)
            .where(
                Location.tenant_id == tenant_id,
                Location.exposure_version_id == exposure_version_id,
            )
        ).all()
        hazard_by_location: Dict[int, List[Dict[str, Any]]] = {}
        for loc_id, attrs in hazard_rows:
            hazard_by_location.setdefault(loc_id, []).append(attrs or {})

        rollup_items: List[RollupResultItem] = []
        if rollup_result_id:
            rollup_result = session.get(RollupResult, rollup_result_id)
            if rollup_result and rollup_result.tenant_id == tenant_id:
                rollup_items = session.query(RollupResultItem).filter(
                    RollupResultItem.tenant_id == tenant_id,
                    RollupResultItem.rollup_result_id == rollup_result_id,
                ).all()

        total_items = len(locations) + len(rollup_items)
        _update_progress(session, run, processed=0, total=total_items)

        now = datetime.utcnow()
        opened = 0
        resolved = 0
        processed_locations = 0

        for rule in location_rules:
            session.refresh(run)
            if run.status == RunStatus.CANCELLED:
                return
            matches: List[Dict[str, Any]] = []
            for loc in locations:
                record = build_location_record(loc, hazard_by_location.get(loc.id, []))
                matched, eval_explanation = evaluate_rule(rule.rule_json, record)
                if matched:
                    matches.append(
                        {"location": loc, "record": record, "evaluation": eval_explanation}
                    )
            matches.sort(key=lambda m: m["location"].id)
            matched_ids = {m["location"].id for m in matches}
            disposition = _uw_rule_disposition(rule.rule_json)
            for match in matches:
                explanation_json = _build_uw_explanation(rule, match["record"], match["evaluation"])
                finding = session.execute(
                    select(UWFinding).where(
                        UWFinding.tenant_id == tenant_id,
                        UWFinding.uw_rule_id == rule.id,
                        UWFinding.exposure_version_id == exposure_version_id,
                        UWFinding.location_id == match["location"].id,
                    )
                ).scalar_one_or_none()
                if not finding:
                    finding = UWFinding(
                        tenant_id=tenant_id,
                        exposure_version_id=exposure_version_id,
                        location_id=match["location"].id,
                        rollup_result_id=rollup_result_id,
                        uw_rule_id=rule.id,
                        status="OPEN",
                        disposition=disposition,
                        explanation_json=explanation_json,
                        first_seen_at=now,
                        last_seen_at=now,
                        resolved_at=None,
                        last_eval_run_id=run_id,
                    )
                    session.add(finding)
                    opened += 1
                else:
                    finding.disposition = disposition
                    finding.explanation_json = explanation_json
                    finding.last_seen_at = now
                    finding.last_eval_run_id = run_id
                    if finding.status == "RESOLVED":
                        finding.status = "OPEN"
                        finding.resolved_at = None
                        opened += 1
            session.commit()
            stale_conditions = [
                UWFinding.tenant_id == tenant_id,
                UWFinding.uw_rule_id == rule.id,
                UWFinding.exposure_version_id == exposure_version_id,
                UWFinding.location_id.isnot(None),
            ]
            if matched_ids:
                stale_conditions.append(~UWFinding.location_id.in_(matched_ids))
            stale_findings = session.execute(select(UWFinding).where(*stale_conditions)).scalars().all()
            for finding in stale_findings:
                if finding.status in ("OPEN", "ACKED"):
                    finding.status = "RESOLVED"
                    finding.resolved_at = now
                    finding.last_seen_at = now
                    finding.last_eval_run_id = run_id
                    resolved += 1
            session.commit()
        if locations:
            processed_locations = len(locations)
            _update_progress(session, run, processed=processed_locations, total=total_items)

        for rule in rollup_rules:
            session.refresh(run)
            if run.status == RunStatus.CANCELLED:
                return
            if not rollup_items:
                continue
            matches = []
            for item in rollup_items:
                record = build_rollup_record(item.rollup_key_json, item.metrics_json)
                matched, eval_explanation = evaluate_rule(rule.rule_json, record)
                if matched:
                    matches.append(
                        {
                            "rollup_key_hash": item.rollup_key_hash,
                            "rollup_key_json": item.rollup_key_json,
                            "metrics_json": item.metrics_json,
                            "record": record,
                            "evaluation": eval_explanation,
                        }
                    )
            matches.sort(key=lambda m: canonical_json(m["rollup_key_json"]))
            matched_hashes = {m["rollup_key_hash"] for m in matches}
            disposition = _uw_rule_disposition(rule.rule_json)
            for match in matches:
                explanation_json = _build_uw_explanation(rule, match["record"], match["evaluation"])
                explanation_json["rollup_key_json"] = match["rollup_key_json"]
                explanation_json["metrics_json"] = match["metrics_json"]
                finding = session.execute(
                    select(UWFinding).where(
                        UWFinding.tenant_id == tenant_id,
                        UWFinding.uw_rule_id == rule.id,
                        UWFinding.exposure_version_id == exposure_version_id,
                        UWFinding.rollup_key_hash == match["rollup_key_hash"],
                    )
                ).scalar_one_or_none()
                if not finding:
                    finding = UWFinding(
                        tenant_id=tenant_id,
                        exposure_version_id=exposure_version_id,
                        rollup_result_id=rollup_result_id,
                        rollup_key_hash=match["rollup_key_hash"],
                        uw_rule_id=rule.id,
                        status="OPEN",
                        disposition=disposition,
                        explanation_json=explanation_json,
                        first_seen_at=now,
                        last_seen_at=now,
                        resolved_at=None,
                        last_eval_run_id=run_id,
                    )
                    session.add(finding)
                    opened += 1
                else:
                    finding.disposition = disposition
                    finding.explanation_json = explanation_json
                    finding.last_seen_at = now
                    finding.rollup_result_id = rollup_result_id
                    finding.last_eval_run_id = run_id
                    if finding.status == "RESOLVED":
                        finding.status = "OPEN"
                        finding.resolved_at = None
                        opened += 1
            session.commit()
            stale_conditions = [
                UWFinding.tenant_id == tenant_id,
                UWFinding.uw_rule_id == rule.id,
                UWFinding.exposure_version_id == exposure_version_id,
                UWFinding.rollup_key_hash.isnot(None),
            ]
            if matched_hashes:
                stale_conditions.append(~UWFinding.rollup_key_hash.in_(matched_hashes))
            stale_findings = session.execute(select(UWFinding).where(*stale_conditions)).scalars().all()
            for finding in stale_findings:
                if finding.status in ("OPEN", "ACKED"):
                    finding.status = "RESOLVED"
                    finding.resolved_at = now
                    finding.last_seen_at = now
                    finding.rollup_result_id = rollup_result_id
                    finding.last_eval_run_id = run_id
                    resolved += 1
            session.commit()
        if rollup_items:
            _update_progress(
                session,
                run,
                processed=processed_locations + len(rollup_items),
                total=total_items,
            )

        run.status = RunStatus.SUCCEEDED
        run.completed_at = datetime.utcnow()
        run.output_refs_json = merge_run_progress(
            {
                "exposure_version_id": exposure_version_id,
                "rollup_result_id": rollup_result_id,
                "uw_findings_open": opened,
                "uw_findings_resolved": resolved,
                "rules_evaluated": len(rules),
                "location_rules": len(location_rules),
                "rollup_rules": len(rollup_rules),
            },
            processed=total_items,
            total=total_items,
        )
        run.code_version = settings.code_version
        session.commit()
    except Exception:
        run.status = RunStatus.FAILED
        run.completed_at = datetime.utcnow()
        session.commit()
        raise
    finally:
        session.close()


@celery_app.task
def commit_upload(run_id: int, upload_id: str, tenant_id: str, name: str = "Exposure", request_id: Optional[str] = None):
    session = SessionLocal()
    run = session.get(Run, run_id)
    if not run or run.tenant_id != tenant_id:
        return
    try:
        if run.status == RunStatus.CANCELLED:
            return
        _attach_request_id(run, request_id)
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
        _log_task_start("commit_upload", run_id, request_id)
        upload = session.get(ExposureUpload, upload_id)
        if not upload:
            raise ValueError("upload not found")
        mapping = session.get(MappingTemplate, upload.mapping_template_id) if upload.mapping_template_id else None
        tenant = session.get(Tenant, tenant_id)
        key = upload.object_uri.split(f"s3://{settings.minio_bucket}/", 1)[1]
        raw_bytes = get_object(key)
        rows = canonicalize_rows(raw_bytes, mapping.template_json if mapping else {})
        total_rows = len(rows) if hasattr(rows, "__len__") else None
        _update_progress(session, run, processed=0, total=total_rows)
        exposure_version = ExposureVersion(
            tenant_id=tenant_id,
            upload_id=upload_id,
            mapping_template_id=upload.mapping_template_id,
            name=name,
            idempotency_key=run.config_refs_json.get("idempotency_key") if run.config_refs_json else None,
        )
        session.add(exposure_version)
        session.commit()
        locations = []
        for mapped in rows:
            loc_dict = to_location_dict(mapped)
            if not (loc_dict.get("lob") or loc_dict.get("product_code")):
                continue
            locations.append(
                Location(
                    tenant_id=tenant_id,
                    exposure_version_id=exposure_version.id,
                    external_location_id=str(loc_dict.get("external_location_id")),
                    address_line1=loc_dict.get("address_line1"),
                    city=loc_dict.get("city"),
                    state_region=loc_dict.get("state_region"),
                    postal_code=loc_dict.get("postal_code"),
                    country=loc_dict.get("country"),
                    latitude=loc_dict.get("latitude"),
                    longitude=loc_dict.get("longitude"),
                    currency=(loc_dict.get("currency") or (tenant.default_currency if tenant else None)),
                    lob=loc_dict.get("lob"),
                    product_code=loc_dict.get("product_code"),
                    tiv=loc_dict.get("tiv"),
                    limit=loc_dict.get("limit"),
                    premium=loc_dict.get("premium"),
                )
            )
        session.bulk_save_objects(locations)
        session.commit()
        run.status = RunStatus.SUCCEEDED
        run.completed_at = datetime.utcnow()
        run.output_refs_json = merge_run_progress(
            {"exposure_version_id": exposure_version.id},
            processed=total_rows,
            total=total_rows,
        )
        run.code_version = settings.code_version
        session.commit()
        return {"exposure_version_id": exposure_version.id, "run_id": run.id}
    except Exception:
        run.status = RunStatus.FAILED
        run.completed_at = datetime.utcnow()
        session.commit()
        raise
    finally:
        session.close()


@celery_app.task
def geocode_and_score(run_id: int, exposure_version_id: int, tenant_id: str, request_id: Optional[str] = None):
    session = SessionLocal()
    run = session.get(Run, run_id)
    if not run or run.tenant_id != tenant_id:
        return
    try:
        if run.status == RunStatus.CANCELLED:
            return
        _attach_request_id(run, request_id)
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
        _log_task_start("geocode_and_score", run_id, request_id)
        locations = session.query(Location).filter(
            Location.exposure_version_id == exposure_version_id,
            Location.tenant_id == tenant_id,
        ).all()
        total_locations = len(locations)
        _update_progress(session, run, processed=0, total=total_locations)
        for loc in locations:
            if loc.latitude is None or loc.longitude is None:
                lat, lon, conf, method = geocode_address(
                    loc.address_line1 or "", loc.city or "", loc.country or ""
                )
                loc.latitude = lat
                loc.longitude = lon
                loc.geocode_method = method
                loc.geocode_confidence = conf
            elif loc.geocode_confidence is None:
                loc.geocode_method = "PROVIDED"
                loc.geocode_confidence = 1.0
            scores = quality_scores({
                "address_line1": loc.address_line1,
                "tiv": loc.tiv,
                "geocode_confidence": loc.geocode_confidence,
            })
            loc.quality_tier = scores["quality_tier"]
            loc.quality_reasons_json = scores["reasons"]
            loc.updated_at = datetime.utcnow()
        session.commit()
        run.status = RunStatus.SUCCEEDED
        run.completed_at = datetime.utcnow()
        run.output_refs_json = merge_run_progress(
            {"exposure_version_id": exposure_version_id},
            processed=total_locations,
            total=total_locations,
        )
        run.code_version = settings.code_version
        session.commit()
    except Exception:
        run.status = RunStatus.FAILED
        run.completed_at = datetime.utcnow()
        session.commit()
        raise
    finally:
        session.close()


@celery_app.task
def overlay_hazard(
    run_id: int,
    overlay_result_id: int,
    exposure_version_id: int,
    hazard_dataset_version_id: int,
    tenant_id: str,
    params: Dict | None = None,
    request_id: Optional[str] = None,
):
    session = SessionLocal()
    run = session.get(Run, run_id)
    overlay_result = session.get(HazardOverlayResult, overlay_result_id)
    if not run or not overlay_result or run.tenant_id != tenant_id or overlay_result.tenant_id != tenant_id:
        return
    try:
        if run.status == RunStatus.CANCELLED:
            return
        _attach_request_id(run, request_id)
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
        _log_task_start("overlay_hazard", run_id, request_id)
        ev = session.get(ExposureVersion, exposure_version_id)
        if not ev:
            raise ValueError("exposure version not found")
        hdv = session.get(HazardDatasetVersion, hazard_dataset_version_id)
        if not hdv or hdv.tenant_id != tenant_id:
            raise ValueError("hazard dataset version not found")
        hazard_dataset = session.get(HazardDataset, hdv.hazard_dataset_id)
        locations = session.query(Location).filter(
            Location.tenant_id == tenant_id,
            Location.exposure_version_id == exposure_version_id,
        ).all()
        total_locations = len(locations)
        _update_progress(session, run, processed=0, total=total_locations)
        saved_attrs = []
        processed = 0
        for loc in locations:
            if loc.latitude is None or loc.longitude is None:
                processed += 1
                continue
            geom_point = func.ST_SetSRID(func.ST_MakePoint(loc.longitude, loc.latitude), 4326)
            features = (
                session.query(HazardFeaturePolygon)
                .filter(
                    HazardFeaturePolygon.tenant_id == tenant_id,
                    HazardFeaturePolygon.hazard_dataset_version_id == hazard_dataset_version_id,
                    func.ST_Contains(HazardFeaturePolygon.geom, geom_point),
                )
                .all()
            )
            if not features:
                continue
            hazards: Dict[str, Dict] = {}
            for feature in features:
                entry = extract_hazard_entry(
                    feature.properties_json or {},
                    hazard_dataset.peril if hazard_dataset else None,
                    hazard_dataset.name if hazard_dataset else str(hdv.hazard_dataset_id),
                    hdv.version_label,
                )
                merge_worst_in_peril(hazards, entry, tie_breaker_id=feature.id)
            if not hazards:
                continue
            best_entry = None
            for entry in hazards.values():
                entry_score = entry.get("score")
                if best_entry is None:
                    best_entry = entry
                    continue
                best_score = best_entry.get("score")
                if best_score is None and entry_score is not None:
                    best_entry = entry
                    continue
                if entry_score is None:
                    continue
                if best_score is None or entry_score > best_score:
                    best_entry = entry
                    continue
                if entry_score == best_score:
                    entry_id = entry.get("_tie_breaker_id")
                    best_id = best_entry.get("_tie_breaker_id")
                    if entry_id is not None and best_id is not None and entry_id < best_id:
                        best_entry = entry
            if not best_entry:
                continue
            props = best_entry.get("raw") or {}
            attributes = {
                "hazard_category": best_entry.get("peril"),
                "band": best_entry.get("band"),
                "percentile": props.get("percentile"),
                "score": best_entry.get("score"),
                "source": best_entry.get("source"),
                "method": "POSTGIS_SPATIAL_JOIN",
                "raw": props,
            }
            saved_attrs.append(
                LocationHazardAttribute(
                    tenant_id=tenant_id,
                    location_id=loc.id,
                    hazard_overlay_result_id=overlay_result.id,
                    attributes_json=attributes,
                )
            )
            processed += 1
            if processed % 200 == 0:
                _update_progress(session, run, processed=processed, total=total_locations)
        if saved_attrs:
            session.bulk_save_objects(saved_attrs)
        session.commit()
        run.status = RunStatus.SUCCEEDED
        run.completed_at = datetime.utcnow()
        run.output_refs_json = merge_run_progress(
            {
                "hazard_overlay_result_id": overlay_result.id,
                "summary": {
                    "locations": len(locations),
                    "attributes_created": len(saved_attrs),
                },
            },
            processed=processed,
            total=total_locations,
        )
        run.code_version = settings.code_version
        session.commit()
    except Exception:
        run.status = RunStatus.FAILED
        run.completed_at = datetime.utcnow()
        session.commit()
        raise
    finally:
        session.close()


@celery_app.task
def compute_resilience_scores(
    run_id: int,
    score_result_id: int,
    exposure_version_id: int,
    hazard_dataset_version_ids: List[int],
    tenant_id: str,
    config: Optional[Dict] = None,
    request_id: Optional[str] = None,
):
    session = SessionLocal()
    run = session.get(Run, run_id)
    score_result = session.get(ResilienceScoreResult, score_result_id)
    if (
        not run
        or not score_result
        or run.tenant_id != tenant_id
        or score_result.tenant_id != tenant_id
    ):
        return
    try:
        if run.status == RunStatus.CANCELLED:
            return
        _attach_request_id(run, request_id)
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
        _log_task_start("compute_resilience_scores", run_id, request_id)
        locations = session.query(Location).filter(
            Location.tenant_id == tenant_id,
            Location.exposure_version_id == exposure_version_id,
        ).all()
        total_locations = len(locations)
        _update_progress(session, run, processed=0, total=total_locations)
        scored = 0
        skipped_missing_coords = 0
        with_structural_count = 0
        without_structural_count = 0
        unknown_hazard_fallback_used_count = 0
        missing_tiv_count = 0
        perils = list(DEFAULT_WEIGHTS.keys())
        peril_coverage = init_peril_coverage(perils)
        batch_size = 1000
        batch: List[ResilienceScoreItem] = []
        version_ids = hazard_dataset_version_ids or []

        for loc in locations:
            if loc.latitude is None or loc.longitude is None:
                skipped_missing_coords += 1
                continue
            if loc.tiv is None:
                missing_tiv_count += 1
            structural = normalize_structural(loc.structural_json)
            if structural:
                with_structural_count += 1
            else:
                without_structural_count += 1
            hazards: Dict[str, Dict] = {}
            if version_ids:
                geom_point = func.ST_SetSRID(func.ST_MakePoint(loc.longitude, loc.latitude), 4326)
                rows = session.execute(
                    select(HazardFeaturePolygon, HazardDatasetVersion, HazardDataset)
                    .join(
                        HazardDatasetVersion,
                        HazardFeaturePolygon.hazard_dataset_version_id == HazardDatasetVersion.id,
                    )
                    .join(HazardDataset, HazardDatasetVersion.hazard_dataset_id == HazardDataset.id)
                    .where(
                        HazardFeaturePolygon.tenant_id == tenant_id,
                        HazardDatasetVersion.tenant_id == tenant_id,
                        HazardDataset.tenant_id == tenant_id,
                        HazardFeaturePolygon.hazard_dataset_version_id.in_(version_ids),
                        func.ST_Contains(HazardFeaturePolygon.geom, geom_point),
                    )
                ).all()
                for feature, version, dataset in rows:
                    entry = extract_hazard_entry(
                        feature.properties_json or {},
                        dataset.peril,
                        dataset.name,
                        version.version_label,
                    )
                    merge_worst_in_peril(hazards, entry, tie_breaker_id=feature.id)
            update_peril_coverage(peril_coverage, hazards, perils)
            fallback_used = any(
                peril not in hazards or hazards.get(peril, {}).get("score") is None
                for peril in perils
            )
            if fallback_used:
                unknown_hazard_fallback_used_count += 1

            normalized_hazards = {
                peril: {k: v for k, v in entry.items() if k != "_tie_breaker_id"}
                for peril, entry in hazards.items()
            }
            result_payload = compute_resilience_score(normalized_hazards, structural, config)
            result_with_input = dict(result_payload)
            result_with_input["input_structural"] = structural
            batch.append(
                ResilienceScoreItem(
                    tenant_id=tenant_id,
                    resilience_score_result_id=score_result_id,
                    location_id=loc.id,
                    resilience_score=result_payload["resilience_score"],
                    risk_score=result_payload["risk_score"],
                    hazards_json=normalized_hazards,
                    result_json=result_with_input,
                )
            )
            scored += 1

            if len(batch) >= batch_size:
                session.bulk_save_objects(batch)
                session.commit()
                batch = []
                _update_progress(session, run, processed=scored + skipped_missing_coords, total=total_locations)

        if batch:
            session.bulk_save_objects(batch)
            session.commit()

        run.status = RunStatus.SUCCEEDED
        run.completed_at = datetime.utcnow()
        run.output_refs_json = merge_run_progress(
            {
                "resilience_score_result_id": score_result_id,
                "scored": scored,
                "skipped_missing_coords": skipped_missing_coords,
                "with_structural_count": with_structural_count,
                "without_structural_count": without_structural_count,
                "peril_coverage": peril_coverage,
                "unknown_hazard_fallback_used_count": unknown_hazard_fallback_used_count,
                "missing_tiv_count": missing_tiv_count,
            },
            processed=scored + skipped_missing_coords,
            total=total_locations,
        )
        run.code_version = settings.code_version
        session.commit()
    except Exception:
        run.status = RunStatus.FAILED
        run.completed_at = datetime.utcnow()
        session.commit()
        raise
    finally:
        session.close()


@celery_app.task
def enrich_property_profile(
    run_id: int,
    tenant_id: str,
    address_json: Dict,
    location_id: Optional[int] = None,
    force_refresh: bool = False,
    request_id: Optional[str] = None,
):
    session = SessionLocal()
    run = session.get(Run, run_id)
    if not run or run.tenant_id != tenant_id:
        return
    try:
        if run.status == RunStatus.CANCELLED:
            return
        _attach_request_id(run, request_id)
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
        _log_task_start("enrich_property_profile", run_id, request_id)
        _update_progress(session, run, processed=0, total=1)

        normalized = normalize_address(address_json)
        fingerprint = address_fingerprint(normalized)
        profile_by_fingerprint = session.execute(
            select(PropertyProfile).where(
                PropertyProfile.tenant_id == tenant_id,
                PropertyProfile.address_fingerprint == fingerprint,
            )
        ).scalar_one_or_none()
        profile_by_location = None
        if location_id is not None:
            profile_by_location = session.execute(
                select(PropertyProfile).where(
                    PropertyProfile.tenant_id == tenant_id,
                    PropertyProfile.location_id == location_id,
                )
            ).scalar_one_or_none()
        if profile_by_fingerprint and is_profile_fresh(profile_by_fingerprint.updated_at) and not force_refresh:
            run.status = RunStatus.SUCCEEDED
            run.completed_at = datetime.utcnow()
            run.output_refs_json = merge_run_progress(
                {
                    "property_profile_id": profile_by_fingerprint.id,
                    "address_fingerprint": fingerprint,
                    "providers": (profile_by_fingerprint.provenance_json or {}).get("providers"),
                    "field_coverage": {
                        key: key in (profile_by_fingerprint.structural_json or {}) for key in STRUCTURAL_KEYS
                    },
                },
                processed=1,
                total=1,
            )
            run.code_version = settings.code_version
            session.commit()
            return

        if profile_by_location and profile_by_fingerprint and profile_by_location.id != profile_by_fingerprint.id:
            profile_by_location.location_id = None

        profile = profile_by_fingerprint or profile_by_location
        if not profile:
            profile = PropertyProfile(tenant_id=tenant_id, address_fingerprint=fingerprint)

        payload = run_enrichment_pipeline(address_json)
        profile.address_fingerprint = payload["address_fingerprint"]
        profile.standardized_address_json = payload["standardized_address_json"]
        profile.geocode_json = payload["geocode_json"]
        profile.parcel_json = payload["parcel_json"]
        profile.characteristics_json = payload["characteristics_json"]
        profile.structural_json = payload["structural_json"]
        profile.provenance_json = payload["provenance_json"]
        profile.code_version = payload["code_version"]
        if location_id is not None:
            profile.location_id = location_id
        session.add(profile)
        session.commit()

        if location_id is not None:
            location = session.get(Location, location_id)
            if location and location.tenant_id == tenant_id:
                standardized = profile.standardized_address_json or {}
                if location.address_line1 is None and standardized.get("address_line1"):
                    location.address_line1 = standardized.get("address_line1")
                if location.city is None and standardized.get("city"):
                    location.city = standardized.get("city")
                if location.state_region is None and standardized.get("state_region"):
                    location.state_region = standardized.get("state_region")
                if location.postal_code is None and standardized.get("postal_code"):
                    location.postal_code = standardized.get("postal_code")
                if location.country is None and standardized.get("country"):
                    location.country = standardized.get("country")
                geocode = profile.geocode_json or {}
                if location.latitude is None and geocode.get("lat") is not None:
                    location.latitude = geocode.get("lat")
                if location.longitude is None and geocode.get("lon") is not None:
                    location.longitude = geocode.get("lon")
                profile_struct = normalize_structural(profile.structural_json)
                if profile_struct:
                    existing_struct = normalize_structural(location.structural_json)
                    location.structural_json = merge_structural(profile_struct, existing_struct)
                location.updated_at = datetime.utcnow()
                session.commit()

        field_coverage = {key: key in (profile.structural_json or {}) for key in STRUCTURAL_KEYS}
        run.status = RunStatus.SUCCEEDED
        run.completed_at = datetime.utcnow()
        run.output_refs_json = merge_run_progress(
            {
                "property_profile_id": profile.id,
                "address_fingerprint": fingerprint,
                "providers": (profile.provenance_json or {}).get("providers"),
                "field_coverage": field_coverage,
            },
            processed=1,
            total=1,
        )
        run.code_version = settings.code_version
        session.add(
            AuditEvent(
                tenant_id=tenant_id,
                user_id=None,
                action="property_enriched",
                metadata_json={"property_profile_id": profile.id, "location_id": location_id},
            )
        )
        session.commit()
    except Exception:
        run.status = RunStatus.FAILED
        run.completed_at = datetime.utcnow()
        session.commit()
        raise
    finally:
        session.close()


@celery_app.task
def drift_compare(
    run_id: int,
    drift_run_id: int,
    exposure_version_a_id: int,
    exposure_version_b_id: int,
    tenant_id: str,
    request_id: Optional[str] = None,
):
    session = SessionLocal()
    run = session.get(Run, run_id)
    drift_run = session.get(DriftRun, drift_run_id)
    if not run or not drift_run or run.tenant_id != tenant_id or drift_run.tenant_id != tenant_id:
        return
    try:
        if run.status == RunStatus.CANCELLED:
            return
        _attach_request_id(run, request_id)
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
        _log_task_start("drift_compare", run_id, request_id)
        locs_a = session.query(Location).filter(
            Location.tenant_id == tenant_id, Location.exposure_version_id == exposure_version_a_id
        ).all()
        locs_b = session.query(Location).filter(
            Location.tenant_id == tenant_id, Location.exposure_version_id == exposure_version_b_id
        ).all()
        _update_progress(session, run, processed=0, total=len(locs_a) + len(locs_b))
        loc_dict_a = [
            {field: getattr(l, field) for field in COMPARE_FIELDS}
            for l in locs_a
        ]
        loc_dict_b = [
            {field: getattr(l, field) for field in COMPARE_FIELDS}
            for l in locs_b
        ]
        summary, details, artifact_bytes, checksum = compare_exposures(loc_dict_a, loc_dict_b, drift_run.config_json or {})
        key = f"drift/{tenant_id}/{drift_run_id}/details.json"
        uri = put_object(key, artifact_bytes, content_type="application/json")
        drift_run.storage_uri = uri
        drift_run.checksum = checksum
        detail_rows = [
            DriftDetail(
                tenant_id=tenant_id,
                drift_run_id=drift_run_id,
                external_location_id=d["external_location_id"],
                classification=d["classification"],
                delta_json=d["delta_json"],
            )
            for d in details
        ]
        if detail_rows:
            session.bulk_save_objects(detail_rows)
        session.commit()
        run.status = RunStatus.SUCCEEDED
        run.completed_at = datetime.utcnow()
        run.output_refs_json = merge_run_progress(
            {
                "drift_run_id": drift_run_id,
                "storage_uri": uri,
                "checksum": checksum,
                "summary": summary,
            },
            processed=len(locs_a) + len(locs_b),
            total=len(locs_a) + len(locs_b),
        )
        run.artifact_checksums_json = {"drift_details": checksum}
        run.code_version = settings.code_version
        session.commit()
    except Exception:
        run.status = RunStatus.FAILED
        run.completed_at = datetime.utcnow()
        session.commit()
        raise
    finally:
        session.close()
