import io
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

import jwt
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Header
from sqlalchemy import func, select, or_, and_
from sqlalchemy.orm import Session

from app.core.auth import TokenData, create_access_token, require_role, verify_password
from app.core.config import get_settings
from app.db import get_db
from app.jobs.celery_app import commit_upload as commit_task
from app.jobs.celery_app import validate_upload as validate_task
from app.jobs.celery_app import geocode_and_score as geocode_task
from app.models import (
    AuditEvent,
    ExposureUpload,
    ExposureVersion,
    Location,
    MappingTemplate,
    Run,
    RunStatus,
    RunType,
    Tenant,
    User,
    UserRole,
    ValidationResult,
    HazardDataset,
    HazardDatasetVersion,
    HazardFeaturePolygon,
    HazardOverlayResult,
    LocationHazardAttribute,
)
from app.storage.s3 import compute_checksum, put_object, get_object
from app.jobs.celery_app import overlay_hazard as overlay_task

router = APIRouter()
settings = get_settings()


def emit_audit(session: Session, tenant_id: str, user_id: Optional[str], action: str, metadata: Optional[dict] = None):
    event = AuditEvent(tenant_id=tenant_id, user_id=user_id, action=action, metadata=metadata or {})
    session.add(event)
    session.commit()


class MappingRequest(BaseModel):
    name: str = "default"
    mapping_json: Dict[str, str]


class HazardDatasetCreate(BaseModel):
    name: str
    peril: str
    vendor: Optional[str] = None
    coverage_geo: Optional[str] = None
    license_ref: Optional[str] = None


class HazardOverlayRequest(BaseModel):
    exposure_version_id: int
    hazard_dataset_version_ids: List[int]
    params: Optional[Dict[str, Any]] = None


@router.post("/auth/login")
def login(payload: Dict[str, str], db: Session = Depends(get_db)) -> Dict[str, str]:
    email = payload.get("email")
    password = payload.get("password")
    tenant_id = payload.get("tenant_id")
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if tenant_id and user.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid tenant")
    if not verify_password(password or "", user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(tenant_id=user.tenant_id, role=user.role.value, user_id=user.id)
    emit_audit(db, user.tenant_id, user.id, "login")
    return {"access_token": token, "token_type": "bearer"}


@router.post("/uploads")
def create_upload(
    file: UploadFile = File(...),
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value)),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
) -> Dict[str, Any]:
    existing = None
    if idempotency_key:
        existing = db.execute(
            select(ExposureUpload).where(
                ExposureUpload.tenant_id == user.tenant_id,
                ExposureUpload.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
    if existing:
        return {"upload_id": existing.id, "object_uri": existing.object_uri}

    content = file.file.read()
    checksum = compute_checksum(content)
    upload_id = str(uuid.uuid4())
    key = f"uploads/{user.tenant_id}/{upload_id}/{file.filename}"
    uri = put_object(key, content, content_type=file.content_type or "text/csv")
    upload = ExposureUpload(
        id=upload_id,
        tenant_id=user.tenant_id,
        filename=file.filename,
        object_uri=uri,
        checksum=checksum,
        idempotency_key=idempotency_key,
        created_by=user.user_id,
    )
    db.add(upload)
    db.commit()
    emit_audit(db, user.tenant_id, user.user_id, "upload_created", {"upload_id": upload_id})
    return {"upload_id": upload_id, "object_uri": uri}


@router.post("/uploads/{upload_id}/mapping")
def attach_mapping(
    upload_id: str,
    mapping_req: MappingRequest,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    upload = db.get(ExposureUpload, upload_id)
    if not upload or upload.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")
    current_version = db.execute(
        select(func.max(MappingTemplate.version)).where(
            MappingTemplate.tenant_id == user.tenant_id, MappingTemplate.name == mapping_req.name
        )
    ).scalar()
    template = MappingTemplate(
        tenant_id=user.tenant_id,
        name=mapping_req.name,
        version=(current_version or 0) + 1,
        template_json=mapping_req.mapping_json,
        created_by=user.user_id,
    )
    db.add(template)
    db.commit()
    upload.mapping_template_id = template.id
    db.commit()
    emit_audit(db, user.tenant_id, user.user_id, "mapping_attached", {"upload_id": upload_id})
    return {"mapping_template_id": template.id, "name": template.name, "version": template.version}


@router.post("/uploads/{upload_id}/validate")
def trigger_validate(
    upload_id: str,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    upload = db.get(ExposureUpload, upload_id)
    if not upload or upload.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")
    run = Run(
        tenant_id=user.tenant_id,
        run_type=RunType.VALIDATION,
        status=RunStatus.QUEUED,
        input_refs_json={"upload_id": upload_id},
        config_refs_json={"mapping_template_id": upload.mapping_template_id},
        created_by=user.user_id,
        code_version=settings.code_version,
    )
    db.add(run)
    db.commit()
    validate_task.delay(run.id, upload_id, user.tenant_id)
    emit_audit(db, user.tenant_id, user.user_id, "validation_requested", {"upload_id": upload_id})
    return {"run_id": run.id, "status": run.status}


@router.post("/uploads/{upload_id}/commit")
def trigger_commit(
    upload_id: str,
    name: Optional[str] = None,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    upload = db.get(ExposureUpload, upload_id)
    if not upload or upload.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")
    existing = db.execute(
        select(ExposureVersion).where(
            ExposureVersion.tenant_id == user.tenant_id,
            ExposureVersion.upload_id == upload_id,
            ExposureVersion.mapping_template_id == upload.mapping_template_id,
        )
    ).scalar_one_or_none()
    if existing:
        response = {"exposure_version_id": existing.id, "note": "existing_exposure_version_returned"}
        return response
    if idempotency_key:
        existing_key = db.execute(
            select(ExposureVersion).where(
                ExposureVersion.tenant_id == user.tenant_id,
                ExposureVersion.upload_id == upload_id,
                ExposureVersion.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing_key:
            return {"exposure_version_id": existing_key.id, "note": "existing_exposure_version_returned"}
    latest_vr = db.execute(
        select(ValidationResult).where(
            ValidationResult.upload_id == upload_id,
            ValidationResult.tenant_id == user.tenant_id,
        ).order_by(ValidationResult.created_at.desc())
    ).scalar_one_or_none()
    if not latest_vr or latest_vr.summary_json.get("ERROR"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Validation errors present")
    run = Run(
        tenant_id=user.tenant_id,
        run_type=RunType.COMMIT,
        status=RunStatus.QUEUED,
        input_refs_json={"upload_id": upload_id},
        config_refs_json={"mapping_template_id": upload.mapping_template_id, "idempotency_key": idempotency_key},
        created_by=user.user_id,
        code_version=settings.code_version,
    )
    db.add(run)
    db.commit()
    commit_task.delay(run.id, upload_id, user.tenant_id, name or f"Exposure {upload_id}")
    emit_audit(db, user.tenant_id, user.user_id, "commit_requested", {"upload_id": upload_id})
    return {"run_id": run.id, "status": run.status}


@router.get("/exposure-versions")
def list_exposure_versions(user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    rows = db.execute(select(ExposureVersion).where(ExposureVersion.tenant_id == user.tenant_id)).scalars().all()
    return {"items": [
        {"id": ev.id, "name": ev.name, "upload_id": ev.upload_id, "created_at": ev.created_at.isoformat()}
        for ev in rows
    ]}


@router.get("/exposure-versions/{exposure_version_id}/summary")
def exposure_summary(exposure_version_id: int, user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    ev = db.get(ExposureVersion, exposure_version_id)
    if not ev or ev.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    count = db.execute(select(func.count()).select_from(Location).where(Location.exposure_version_id == ev.id, Location.tenant_id == user.tenant_id)).scalar_one()
    tiv_sum = db.execute(select(func.sum(Location.tiv)).where(Location.exposure_version_id == ev.id, Location.tenant_id == user.tenant_id)).scalar()
    return {"exposure_version_id": ev.id, "locations": count, "tiv": tiv_sum or 0}


@router.get("/exposure-versions/{exposure_version_id}/locations")
def exposure_locations(exposure_version_id: int, user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    ev = db.get(ExposureVersion, exposure_version_id)
    if not ev or ev.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    rows = db.execute(select(Location).where(Location.exposure_version_id == ev.id, Location.tenant_id == user.tenant_id)).scalars().all()
    return {"items": [
        {
            "external_location_id": r.external_location_id,
            "address_line1": r.address_line1,
            "city": r.city,
            "country": r.country,
            "latitude": r.latitude,
            "longitude": r.longitude,
        }
        for r in rows
    ]}


@router.get("/exposure-versions/{exposure_version_id}/exceptions")
def exposure_exceptions(exposure_version_id: int, user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    ev = db.get(ExposureVersion, exposure_version_id)
    if not ev or ev.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    vr = db.execute(
        select(ValidationResult)
        .where(ValidationResult.upload_id == ev.upload_id, ValidationResult.tenant_id == user.tenant_id)
        .order_by(ValidationResult.created_at.desc())
    ).scalar_one_or_none()
    if not vr:
        issues = []
    else:
        issues = json.loads(get_object(vr.row_errors_uri.split(f"s3://{settings.minio_bucket}/", 1)[1]).decode())
    quality_rows = db.execute(
        select(Location).where(
            Location.exposure_version_id == ev.id,
            Location.tenant_id == user.tenant_id,
            or_(
                Location.quality_tier == "C",
                and_(Location.geocode_confidence.isnot(None), Location.geocode_confidence < 0.6),
            ),
        )
    ).scalars().all()
    items = []
    for loc in quality_rows:
        items.append({
            "type": "QUALITY_TIER_C" if (loc.quality_tier == "C") else "LOW_GEO_CONFIDENCE",
            "external_location_id": loc.external_location_id,
            "quality_tier": loc.quality_tier,
            "reasons": loc.quality_reasons_json or [],
            "geocode_confidence": loc.geocode_confidence,
        })
    for issue in issues:
        items.append({"type": "VALIDATION_ISSUE", **issue})
    return {"items": items}


@router.post("/exposure-versions/{exposure_version_id}/geocode")
def trigger_geocode(
    exposure_version_id: int,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ev = db.get(ExposureVersion, exposure_version_id)
    if not ev or ev.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    run = Run(
        tenant_id=user.tenant_id,
        run_type=RunType.GEOCODE,
        status=RunStatus.QUEUED,
        input_refs_json={"exposure_version_id": exposure_version_id},
        created_by=user.user_id,
        code_version=settings.code_version,
    )
    db.add(run)
    db.commit()
    geocode_task.delay(run.id, exposure_version_id, user.tenant_id)
    return {"run_id": run.id, "status": run.status}


@router.post("/hazard-datasets")
def create_hazard_dataset(
    payload: HazardDatasetCreate,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    dataset = HazardDataset(
        tenant_id=user.tenant_id,
        name=payload.name,
        peril=payload.peril,
        vendor=payload.vendor,
        coverage_geo=payload.coverage_geo,
        license_ref=payload.license_ref,
    )
    db.add(dataset)
    db.commit()
    return {"hazard_dataset_id": dataset.id}


@router.get("/hazard-datasets")
def list_hazard_datasets(user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    items = db.execute(select(HazardDataset).where(HazardDataset.tenant_id == user.tenant_id)).scalars().all()
    return {"items": [
        {"id": d.id, "name": d.name, "peril": d.peril, "vendor": d.vendor, "created_at": d.created_at}
        for d in items
    ]}


@router.post("/hazard-datasets/{hazard_dataset_id}/versions")
def upload_hazard_dataset_version(
    hazard_dataset_id: int,
    version_label: str,
    file: UploadFile = File(...),
    effective_date: Optional[str] = None,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    dataset = db.get(HazardDataset, hazard_dataset_id)
    if not dataset or dataset.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    raw = file.file.read()
    checksum = compute_checksum(raw)
    key = f"hazard_datasets/{user.tenant_id}/{hazard_dataset_id}/{version_label}.geojson"
    uri = put_object(key, raw, content_type=file.content_type or "application/geo+json")
    eff_dt = datetime.fromisoformat(effective_date) if effective_date else None
    version = HazardDatasetVersion(
        tenant_id=user.tenant_id,
        hazard_dataset_id=hazard_dataset_id,
        version_label=version_label,
        storage_uri=uri,
        checksum=checksum,
        effective_date=eff_dt,
    )
    db.add(version)
    db.commit()
    geojson = json.loads(raw.decode())
    features = geojson.get("features", [])
    for feature in features:
        geom_json = json.dumps(feature.get("geometry"))
        geometry = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geom_json), 4326)
        db.add(
            HazardFeaturePolygon(
                tenant_id=user.tenant_id,
                hazard_dataset_version_id=version.id,
                geom=geometry,
                properties_json=feature.get("properties"),
            )
        )
    db.commit()
    return {"hazard_dataset_version_id": version.id}


@router.get("/hazard-datasets/{hazard_dataset_id}/versions")
def list_hazard_dataset_versions(hazard_dataset_id: int, user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    versions = db.execute(
        select(HazardDatasetVersion).where(
            HazardDatasetVersion.hazard_dataset_id == hazard_dataset_id,
            HazardDatasetVersion.tenant_id == user.tenant_id,
        )
    ).scalars().all()
    return {"items": [
        {"id": v.id, "version_label": v.version_label, "checksum": v.checksum, "created_at": v.created_at}
        for v in versions
    ]}


@router.post("/hazard-overlays")
def trigger_hazard_overlays(
    payload: HazardOverlayRequest,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ev = db.get(ExposureVersion, payload.exposure_version_id)
    if not ev or ev.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exposure version not found")
    overlay_runs = []
    for hdv_id in payload.hazard_dataset_version_ids:
        version = db.get(HazardDatasetVersion, hdv_id)
        if not version or version.tenant_id != user.tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset version not found")
        run = Run(
            tenant_id=user.tenant_id,
            run_type=RunType.OVERLAY,
            status=RunStatus.QUEUED,
            input_refs_json={"exposure_version_id": payload.exposure_version_id, "hazard_dataset_version_id": hdv_id},
            config_refs_json=payload.params or {},
            created_by=user.user_id,
            code_version=settings.code_version,
        )
        db.add(run)
        db.commit()
        overlay_task.delay(run.id, payload.exposure_version_id, hdv_id, user.tenant_id, payload.params or {})
        overlay_runs.append({"run_id": run.id, "hazard_dataset_version_id": hdv_id})
    return {"overlay_requests": overlay_runs}


@router.get("/hazard-overlays/{overlay_result_id}/status")
def get_overlay_status(overlay_result_id: int, user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    overlay = db.get(HazardOverlayResult, overlay_result_id)
    if not overlay or overlay.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    run = db.get(Run, overlay.run_id) if overlay.run_id else None
    return {
        "hazard_overlay_result_id": overlay.id,
        "run_status": run.status if run else None,
        "created_at": overlay.created_at,
    }


@router.get("/hazard-overlays/{overlay_result_id}/summary")
def overlay_summary(overlay_result_id: int, user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    overlay = db.get(HazardOverlayResult, overlay_result_id)
    if not overlay or overlay.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    total_locations = db.execute(
        select(func.count()).select_from(Location).where(
            Location.tenant_id == user.tenant_id,
            Location.exposure_version_id == overlay.exposure_version_id,
        )
    ).scalar()
    matched = db.execute(
        select(func.count()).select_from(LocationHazardAttribute).where(
            LocationHazardAttribute.tenant_id == user.tenant_id,
            LocationHazardAttribute.hazard_overlay_result_id == overlay.id,
        )
    ).scalar()
    band_counts = db.execute(
        select(LocationHazardAttribute.attributes_json["band"], func.count())
        .where(LocationHazardAttribute.hazard_overlay_result_id == overlay.id)
        .group_by(LocationHazardAttribute.attributes_json["band"])
    ).all()
    return {
        "overlay_result_id": overlay.id,
        "locations": total_locations,
        "matched": matched,
        "band_distribution": {str(band): count for band, count in band_counts},
    }


@router.get("/runs/{run_id}")
def get_run(run_id: int, user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    run = db.get(Run, run_id)
    if not run or run.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return {
        "id": run.id,
        "run_type": run.run_type,
        "status": run.status,
        "input_refs": run.input_refs_json,
        "config_refs": run.config_refs_json,
        "output_refs": run.output_refs_json,
        "artifact_checksums": run.artifact_checksums_json,
        "code_version": run.code_version,
        "created_by": run.created_by,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }


@router.get("/audit-events")
def list_audit_events(user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    events = db.execute(select(AuditEvent).where(AuditEvent.tenant_id == user.tenant_id).order_by(AuditEvent.created_at.desc())).scalars().all()
    return {"items": [
        {"action": e.action, "created_at": e.created_at.isoformat(), "user_id": e.user_id, "metadata": e.metadata}
        for e in events
    ]}


@router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}
