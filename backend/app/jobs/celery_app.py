import csv
import io
import json
from typing import Dict, List

from celery import Celery
from sqlalchemy import select

from app.core.config import get_settings
from app.db import SessionLocal
from app.models import ExposureUpload, Location, MappingTemplate, Run, RunStatus, RunType, ValidationResult, ExposureVersion
from app.storage.s3 import compute_checksum, get_object, put_object

settings = get_settings()

celery_app = Celery(
    "aegis", broker=settings.redis_url, backend=settings.redis_url
)


@celery_app.task
def validate_upload(upload_id: str, tenant_id: str):
    session = SessionLocal()
    run = Run(
        tenant_id=tenant_id,
        run_type=RunType.VALIDATION,
        status=RunStatus.RUNNING,
        config_refs_json={"upload_id": upload_id},
    )
    session.add(run)
    session.commit()
    try:
        upload = session.get(ExposureUpload, upload_id)
        if not upload:
            raise ValueError("upload not found")
        mapping = None
        if upload.mapping_template_id:
            mapping = session.get(MappingTemplate, upload.mapping_template_id)
        key = upload.object_uri.split(f"s3://{settings.minio_bucket}/", 1)[1]
        raw_bytes = get_object(key)
        reader = csv.DictReader(io.StringIO(raw_bytes.decode()))
        errors: List[Dict[str, str]] = []
        summary = {"errors": 0, "warnings": 0, "infos": 0}

        for idx, row in enumerate(reader):
            mapped = row
            if mapping:
                mapped = {dst: row.get(src, "") for src, dst in mapping.template_json.items()}
            row_errors: List[str] = []
            ext_id = mapped.get("external_location_id")
            if not ext_id:
                row_errors.append("missing external_location_id")
            lat = mapped.get("lat") or mapped.get("latitude")
            lon = mapped.get("lon") or mapped.get("longitude")
            address = mapped.get("address_line1")
            city = mapped.get("city")
            country = mapped.get("country")
            if not ((lat and lon) or (address and city and country)):
                row_errors.append("missing location coordinates or address")
            for numeric_field in ["tiv", "limit", "premium"]:
                value = mapped.get(numeric_field)
                if value:
                    try:
                        if float(value) < 0:
                            row_errors.append(f"{numeric_field} negative")
                    except ValueError:
                        row_errors.append(f"{numeric_field} invalid")
            if row_errors:
                summary["errors"] += 1
                errors.append({"row": idx + 1, "errors": row_errors})
        artifact = json.dumps(errors, sort_keys=True)
        key_errs = f"validations/{tenant_id}/{upload_id}/row_errors.json"
        uri = put_object(key_errs, artifact.encode(), content_type="application/json")
        checksum = compute_checksum(artifact.encode())
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
        run.artifact_checksums_json = {"row_errors": checksum}
        session.commit()
        return {"validation_result_id": validation.id, "run_id": run.id}
    except Exception:
        run.status = RunStatus.FAILED
        session.commit()
        raise
    finally:
        session.close()


@celery_app.task
def commit_upload(upload_id: str, tenant_id: str, name: str = "Exposure"):
    session = SessionLocal()
    run = Run(
        tenant_id=tenant_id,
        run_type=RunType.VALIDATION,
        status=RunStatus.RUNNING,
        config_refs_json={"stage": "COMMIT", "upload_id": upload_id},
    )
    session.add(run)
    session.commit()
    try:
        upload = session.get(ExposureUpload, upload_id)
        if not upload:
            raise ValueError("upload not found")
        mapping = session.get(MappingTemplate, upload.mapping_template_id) if upload.mapping_template_id else None
        key = upload.object_uri.split(f"s3://{settings.minio_bucket}/", 1)[1]
        raw_bytes = get_object(key)
        reader = csv.DictReader(io.StringIO(raw_bytes.decode()))
        exposure_version = ExposureVersion(
            tenant_id=tenant_id,
            upload_id=upload_id,
            mapping_template_id=upload.mapping_template_id,
            name=name,
        )
        session.add(exposure_version)
        session.commit()
        locations = []
        for row in reader:
            mapped = row
            if mapping:
                mapped = {dst: row.get(src, "") for src, dst in mapping.template_json.items()}
            locations.append(
                Location(
                    tenant_id=tenant_id,
                    exposure_version_id=exposure_version.id,
                    external_location_id=str(mapped.get("external_location_id")),
                    address_line1=mapped.get("address_line1"),
                    city=mapped.get("city"),
                    country=mapped.get("country"),
                    latitude=float(mapped.get("lat") or 0) if mapped.get("lat") else None,
                    longitude=float(mapped.get("lon") or 0) if mapped.get("lon") else None,
                    tiv=float(mapped.get("tiv")) if mapped.get("tiv") else None,
                    limit=float(mapped.get("limit")) if mapped.get("limit") else None,
                    premium=float(mapped.get("premium")) if mapped.get("premium") else None,
                )
            )
        session.bulk_save_objects(locations)
        session.commit()
        run.status = RunStatus.SUCCEEDED
        session.commit()
        return {"exposure_version_id": exposure_version.id, "run_id": run.id}
    except Exception:
        run.status = RunStatus.FAILED
        session.commit()
        raise
    finally:
        session.close()
