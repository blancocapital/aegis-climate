import io
import json
import uuid
import base64
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
from app.jobs.celery_app import drift_compare as drift_task
from app.models import (
    AuditEvent,
    DriftDetail,
    DriftRun,
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
    RollupConfig,
    RollupResult,
    RollupResultItem,
    ThresholdRule,
    Breach,
)
from app.services.lineage import build_lineage
from app.storage.s3 import compute_checksum, put_object, get_object
from app.jobs.celery_app import overlay_hazard as overlay_task
from app.jobs.celery_app import rollup_execute as rollup_task
from app.jobs.celery_app import breach_evaluate as breach_task

router = APIRouter()
settings = get_settings()


def emit_audit(session: Session, tenant_id: str, user_id: Optional[str], action: str, metadata: Optional[dict] = None):
    event = AuditEvent(tenant_id=tenant_id, user_id=user_id, action=action, metadata_json=metadata or {})
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


class DriftRequest(BaseModel):
    exposure_version_a: int
    exposure_version_b: int
    config: Optional[Dict[str, Any]] = None


class RollupConfigCreate(BaseModel):
    name: str
    dimensions_json: List[str]
    filters_json: Optional[Dict[str, Any]] = None
    measures_json: List[Dict[str, Any]]


class RollupRequest(BaseModel):
    exposure_version_id: int
    rollup_config_id: int
    hazard_overlay_result_ids: List[int]


class ThresholdRuleCreate(BaseModel):
    name: str
    severity: str
    active: bool = True
    rule_json: Dict[str, Any]


class BreachEvalRequest(BaseModel):
    rollup_result_id: int
    threshold_rule_ids: Optional[List[int]] = None


@router.post("/auth/login")
def login(payload: Dict[str, str], db: Session = Depends(get_db)) -> Dict[str, str]:
    email = payload.get("email")
    password = payload.get("password")
    tenant_id = payload.get("tenant_id")
    query = select(User).where(User.email == email)
    if tenant_id:
        query = query.where(User.tenant_id == tenant_id)
        user = db.execute(query).scalar_one_or_none()
    else:
        users = db.execute(query).scalars().all()
        if len(users) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tenant_id required when multiple tenants share this email",
            )
        user = users[0] if users else None
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
    if latest_vr.mapping_template_id != upload.mapping_template_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Validation must match current mapping template",
        )
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
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Geocoding is not implemented for Milestone A",
    )


@router.post("/hazard-datasets")
def create_hazard_dataset(
    payload: HazardDatasetCreate,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Hazard datasets are not implemented for Milestone A",
    )


@router.get("/hazard-datasets")
def list_hazard_datasets(user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Hazard datasets are not implemented for Milestone A",
    )


@router.post("/hazard-datasets/{hazard_dataset_id}/versions")
def upload_hazard_dataset_version(
    hazard_dataset_id: int,
    version_label: str,
    file: UploadFile = File(...),
    effective_date: Optional[str] = None,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Hazard datasets are not implemented for Milestone A",
    )


@router.get("/hazard-datasets/{hazard_dataset_id}/versions")
def list_hazard_dataset_versions(hazard_dataset_id: int, user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Hazard datasets are not implemented for Milestone A",
    )


@router.post("/hazard-overlays")
def trigger_hazard_overlays(
    payload: HazardOverlayRequest,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Hazard overlays are not implemented for Milestone A",
    )


@router.get("/hazard-overlays/{overlay_result_id}/status")
def get_overlay_status(overlay_result_id: int, user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Hazard overlays are not implemented for Milestone A",
    )


@router.get("/hazard-overlays/{overlay_result_id}/summary")
def overlay_summary(overlay_result_id: int, user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Hazard overlays are not implemented for Milestone A",
    )


@router.post("/drift")
def trigger_drift(
    payload: DriftRequest,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Drift is not implemented for Milestone A",
    )


@router.get("/drift/{drift_run_id}")
def get_drift(
    drift_run_id: int,
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Drift is not implemented for Milestone A",
    )


@router.get("/drift/{drift_run_id}/details")
def drift_details(
    drift_run_id: int,
    classification: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Drift is not implemented for Milestone A",
    )


@router.post("/rollup-configs")
def create_rollup_config(
    payload: RollupConfigCreate,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Rollups are not implemented for Milestone A",
    )


@router.get("/rollup-configs")
def list_rollup_configs(user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Rollups are not implemented for Milestone A",
    )


@router.post("/rollups")
def trigger_rollup(
    payload: RollupRequest,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Rollups are not implemented for Milestone A",
    )


@router.get("/rollups/{rollup_result_id}")
def rollup_result_detail(rollup_result_id: int, user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Rollups are not implemented for Milestone A",
    )


@router.get("/rollups/{rollup_result_id}/drilldown")
def rollup_drilldown(
    rollup_result_id: int,
    rollup_key_b64: str,
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Rollups are not implemented for Milestone A",
    )

@router.post("/threshold-rules")
def create_threshold_rule(
    payload: ThresholdRuleCreate,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Threshold rules are not implemented for Milestone A",
    )


@router.get("/threshold-rules")
def list_threshold_rules(user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Threshold rules are not implemented for Milestone A",
    )


@router.post("/breaches/run")
def run_breach_eval(
    payload: BreachEvalRequest,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Breaches are not implemented for Milestone A",
    )


@router.get("/breaches")
def list_breaches(
    status_filter: Optional[str] = None,
    exposure_version_id: Optional[int] = None,
    threshold_rule_id: Optional[int] = None,
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Breaches are not implemented for Milestone A",
    )


@router.patch("/breaches/{breach_id}")
def update_breach_status(
    breach_id: int,
    payload: Dict[str, str],
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Breaches are not implemented for Milestone A",
    )


@router.get("/lineage")
def get_lineage(
    entity_type: str,
    entity_id: int,
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Lineage is not implemented for Milestone A",
    )


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
        {"action": e.action, "created_at": e.created_at.isoformat(), "user_id": e.user_id, "metadata": e.metadata_json}
        for e in events
    ]}


@router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}
