import json
from datetime import datetime
from typing import Dict

from celery import Celery
from sqlalchemy import select

from app.core.config import get_settings
from app.db import SessionLocal
from app.models import ExposureUpload, Location, MappingTemplate, Run, RunStatus, RunType, ValidationResult, ExposureVersion
from app.services.validation import read_csv_bytes, validate_rows
from app.services.commit import canonicalize_rows, to_location_dict
from app.services.geocode import geocode_address
from app.services.quality import quality_scores
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
            locations.append(
                Location(
                    tenant_id=tenant_id,
                    exposure_version_id=exposure_version.id,
                    external_location_id=str(loc_dict.get("external_location_id")),
                    address_line1=loc_dict.get("address_line1"),
                    city=loc_dict.get("city"),
                    country=loc_dict.get("country"),
                    latitude=loc_dict.get("latitude"),
                    longitude=loc_dict.get("longitude"),
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
