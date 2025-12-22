import json
from datetime import datetime
from typing import Dict, List

from datetime import datetime

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
    MappingTemplate,
    RollupConfig,
    RollupResult,
    RollupResultItem,
    Run,
    RunStatus,
    RunType,
    Tenant,
    ThresholdRule,
    ValidationResult,
)
from app.services.validation import read_csv_bytes, validate_rows
from app.services.commit import canonicalize_rows, to_location_dict
from app.services.geocode import geocode_address
from app.services.quality import quality_scores
from app.services.rollup import compute_rollup
from app.services.breaches import evaluate_rule_on_rollup_rows
from app.services.drift import COMPARE_FIELDS, compare_exposures
from app.storage.s3 import compute_checksum, get_object, put_object

settings = get_settings()

celery_app = Celery(
    "aegis", broker=settings.redis_url, backend=settings.redis_url
)


@celery_app.task
def validate_upload(run_id: int, upload_id: str, tenant_id: str):
    session = SessionLocal()
    run = session.get(Run, run_id)
    if not run or run.tenant_id != tenant_id:
        return
    try:
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
        upload = session.get(ExposureUpload, upload_id)
        if not upload:
            raise ValueError("upload not found")
        mapping = session.get(MappingTemplate, upload.mapping_template_id) if upload.mapping_template_id else None
        key = upload.object_uri.split(f"s3://{settings.minio_bucket}/", 1)[1]
        raw_bytes = get_object(key)
        rows = read_csv_bytes(raw_bytes)
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
        run.output_refs_json = {"validation_result_id": validation.id}
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
):
    session = SessionLocal()
    run = session.get(Run, run_id)
    rollup_result = session.get(RollupResult, rollup_result_id)
    if not run or not rollup_result or run.tenant_id != tenant_id or rollup_result.tenant_id != tenant_id:
        return
    try:
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
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
        run.output_refs_json = {"rollup_result_id": rollup_result_id}
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
):
    session = SessionLocal()
    run = session.get(Run, run_id)
    rollup_result = session.get(RollupResult, rollup_result_id)
    if not run or not rollup_result or run.tenant_id != tenant_id or rollup_result.tenant_id != tenant_id:
        return
    try:
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
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
        run.output_refs_json = {
            "rollup_result_id": rollup_result_id,
            "breaches_open": opened,
            "breaches_resolved": resolved,
            "rules_evaluated": len(rules),
        }
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
def commit_upload(run_id: int, upload_id: str, tenant_id: str, name: str = "Exposure"):
    session = SessionLocal()
    run = session.get(Run, run_id)
    if not run or run.tenant_id != tenant_id:
        return
    try:
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
        upload = session.get(ExposureUpload, upload_id)
        if not upload:
            raise ValueError("upload not found")
        mapping = session.get(MappingTemplate, upload.mapping_template_id) if upload.mapping_template_id else None
        tenant = session.get(Tenant, tenant_id)
        key = upload.object_uri.split(f"s3://{settings.minio_bucket}/", 1)[1]
        raw_bytes = get_object(key)
        rows = canonicalize_rows(raw_bytes, mapping.template_json if mapping else {})
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
        run.output_refs_json = {"exposure_version_id": exposure_version.id}
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
def geocode_and_score(run_id: int, exposure_version_id: int, tenant_id: str):
    session = SessionLocal()
    run = session.get(Run, run_id)
    if not run or run.tenant_id != tenant_id:
        return
    try:
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
        locations = session.query(Location).filter(
            Location.exposure_version_id == exposure_version_id,
            Location.tenant_id == tenant_id,
        ).all()
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
        run.output_refs_json = {"exposure_version_id": exposure_version_id}
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
):
    session = SessionLocal()
    run = session.get(Run, run_id)
    overlay_result = session.get(HazardOverlayResult, overlay_result_id)
    if not run or not overlay_result or run.tenant_id != tenant_id or overlay_result.tenant_id != tenant_id:
        return
    try:
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
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
        saved_attrs = []
        for loc in locations:
            if loc.latitude is None or loc.longitude is None:
                continue
            geom_point = func.ST_SetSRID(func.ST_MakePoint(loc.longitude, loc.latitude), 4326)
            feature = (
                session.query(HazardFeaturePolygon)
                .filter(
                    HazardFeaturePolygon.tenant_id == tenant_id,
                    HazardFeaturePolygon.hazard_dataset_version_id == hazard_dataset_version_id,
                    func.ST_Contains(HazardFeaturePolygon.geom, geom_point),
                )
                .order_by(HazardFeaturePolygon.id.asc())
                .first()
            )
            if not feature:
                continue
            props = feature.properties_json or {}
            attributes = {
                "hazard_category": (
                    props.get("hazard_category")
                    or props.get("peril")
                    or props.get("hazard")
                    or (hazard_dataset.peril if hazard_dataset else None)
                ),
                "band": props.get("band") or props.get("Band"),
                "percentile": props.get("percentile"),
                "score": props.get("score"),
                "source": f"{hazard_dataset.name if hazard_dataset else hdv.hazard_dataset_id}:{hdv.version_label}",
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
        if saved_attrs:
            session.bulk_save_objects(saved_attrs)
        session.commit()
        run.status = RunStatus.SUCCEEDED
        run.completed_at = datetime.utcnow()
        run.output_refs_json = {
            "hazard_overlay_result_id": overlay_result.id,
            "summary": {
                "locations": len(locations),
                "attributes_created": len(saved_attrs),
            },
        }
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
def drift_compare(
    run_id: int,
    drift_run_id: int,
    exposure_version_a_id: int,
    exposure_version_b_id: int,
    tenant_id: str,
):
    session = SessionLocal()
    run = session.get(Run, run_id)
    drift_run = session.get(DriftRun, drift_run_id)
    if not run or not drift_run or run.tenant_id != tenant_id or drift_run.tenant_id != tenant_id:
        return
    try:
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        session.commit()
        locs_a = session.query(Location).filter(
            Location.tenant_id == tenant_id, Location.exposure_version_id == exposure_version_a_id
        ).all()
        locs_b = session.query(Location).filter(
            Location.tenant_id == tenant_id, Location.exposure_version_id == exposure_version_b_id
        ).all()
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
        run.output_refs_json = {
            "drift_run_id": drift_run_id,
            "storage_uri": uri,
            "checksum": checksum,
            "summary": summary,
        }
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
