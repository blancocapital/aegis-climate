import io
import json
import uuid
import base64
import time
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

import jwt
from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile, status, Header
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import case, func, select, or_, and_
from sqlalchemy.orm import Session

from app.core.auth import TokenData, create_access_token, require_role, verify_password
from app.core.config import get_settings
from app.core.request_id import get_request_id
from app.db import get_db
from app.jobs.celery_app import celery_app
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
    ResilienceScoreResult,
    ResilienceScoreItem,
    PropertyProfile,
    PolicyPack,
    PolicyPackVersion,
)
from app.services.geocode import geocode_address
from app.services.hazard_query import extract_hazard_entry, merge_worst_in_peril
from app.services.lineage import build_lineage
from app.services.pagination import resolve_keyset_pagination
from app.services.quality_metrics import compute_bucket_percentages
from app.services.request_fingerprint import canonical_json, fingerprint_resilience_scores_request
from app.services.resilience_export import iter_resilience_export_rows
from app.services.resilience import DEFAULT_WEIGHTS, SCORING_VERSION, compute_resilience_score
from app.services.structural import merge_structural, normalize_structural
from app.services.explainability import build_explainability
from app.services.policy_resolver import merge_policy_overrides, resolve_policy_version
from app.services.property_enrichment import (
    determine_enrich_mode,
    normalize_address,
    address_fingerprint,
    providers_are_stub,
    run_enrichment_pipeline,
    is_profile_fresh,
    decide_enrichment_action,
    STRUCTURAL_KEYS,
)
from app.services.underwriting_decision import evaluate_underwriting_decision
from app.storage.s3 import compute_checksum, put_object, get_object
from app.jobs.celery_app import overlay_hazard as overlay_task
from app.jobs.celery_app import rollup_execute as rollup_task
from app.jobs.celery_app import breach_evaluate as breach_task
from app.jobs.celery_app import compute_resilience_scores as resilience_score_task
from app.jobs.celery_app import enrich_property_profile as enrich_property_profile_task

router = APIRouter()
settings = get_settings()


def emit_audit(session: Session, tenant_id: str, user_id: Optional[str], action: str, metadata: Optional[dict] = None):
    event = AuditEvent(tenant_id=tenant_id, user_id=user_id, action=action, metadata_json=metadata or {})
    session.add(event)
    session.commit()


def apply_request_id(run: Run) -> None:
    request_id = get_request_id()
    if request_id:
        run.request_id = request_id


def serialize_run(run: Run) -> Dict[str, Any]:
    return {
        "id": run.id,
        "run_type": run.run_type.value if hasattr(run.run_type, "value") else run.run_type,
        "status": run.status.value if hasattr(run.status, "value") else run.status,
        "input_refs": run.input_refs_json,
        "config_refs": run.config_refs_json,
        "output_refs": run.output_refs_json,
        "artifact_checksums": run.artifact_checksums_json,
        "input_refs_json": run.input_refs_json,
        "config_refs_json": run.config_refs_json,
        "output_refs_json": run.output_refs_json,
        "artifact_checksums_json": run.artifact_checksums_json,
        "code_version": run.code_version,
        "created_by": run.created_by,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "cancelled_at": run.cancelled_at.isoformat() if run.cancelled_at else None,
        "request_id": run.request_id,
        "celery_task_id": run.celery_task_id,
    }


def extract_progress(output_refs_json: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not output_refs_json:
        return None
    processed = output_refs_json.get("processed")
    total = output_refs_json.get("total")
    if processed is None and total is None:
        return None
    return {"processed": processed, "total": total}


def build_hazard_versions(db: Session, tenant_id: str, version_ids: List[int]) -> List[Dict[str, Any]]:
    if not version_ids:
        return []
    rows = db.execute(
        select(HazardDatasetVersion, HazardDataset)
        .join(HazardDataset, HazardDatasetVersion.hazard_dataset_id == HazardDataset.id)
        .where(
            HazardDatasetVersion.tenant_id == tenant_id,
            HazardDataset.tenant_id == tenant_id,
            HazardDatasetVersion.id.in_(version_ids),
        )
        .order_by(HazardDataset.id.asc(), HazardDatasetVersion.id.asc())
    ).all()
    versions = []
    for version, dataset in rows:
        versions.append(
            {
                "hazard_dataset_id": dataset.id,
                "hazard_dataset_name": dataset.name,
                "peril": dataset.peril,
                "hazard_dataset_version_id": version.id,
                "version_label": version.version_label,
                "effective_date": version.effective_date.isoformat() if version.effective_date else None,
                "created_at": version.created_at.isoformat(),
            }
        )
    return versions


def summarize_property_profile(profile: Optional[PropertyProfile]) -> Optional[Dict[str, Any]]:
    if not profile:
        return None
    provenance = profile.provenance_json or {}
    errors = provenance.get("errors") or []
    return {
        "property_profile_id": profile.id,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        "structural_json": profile.structural_json,
        "provenance_summary": {
            "providers": provenance.get("providers"),
            "field_coverage": {key: key in (profile.structural_json or {}) for key in STRUCTURAL_KEYS},
            "errors": errors,
        },
    }


def compute_structural_completeness(structural: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    structural = structural or {}
    return {key: structural.get(key) is not None for key in STRUCTURAL_KEYS}


class MappingRequest(BaseModel):
    name: str = "default"
    mapping_json: Dict[str, str]


class PolicyPackCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class PolicyPackVersionCreate(BaseModel):
    version_label: str
    scoring_config_json: Optional[Dict[str, Any]] = None
    underwriting_policy_json: Optional[Dict[str, Any]] = None


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


class ResilienceStructural(BaseModel):
    roof_material: Optional[str] = None
    elevation_m: Optional[float] = None
    vegetation_proximity_m: Optional[float] = None


class ResilienceScoreRequest(BaseModel):
    location_id: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    address_line1: Optional[str] = None
    city: Optional[str] = None
    state_region: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    structural: Optional[ResilienceStructural] = None
    hazard_dataset_version_ids: Optional[List[int]] = None
    enrich: bool = True
    enrich_mode: str = "auto"
    wait_for_enrichment_seconds: Optional[int] = 0
    best_effort: bool = True
    include_decision: bool = True
    underwriting_policy: Optional[Dict[str, Any]] = None
    policy_pack_version_id: Optional[int] = None


class LocationStructuralRequest(BaseModel):
    structural: Optional[Dict[str, Any]] = None


class ExposureStructuralItem(BaseModel):
    external_location_id: str
    structural: Optional[Dict[str, Any]] = None


class ExposureStructuralBatchRequest(BaseModel):
    items: List[ExposureStructuralItem]


class PropertyProfileResolveRequest(BaseModel):
    address: Dict[str, Any]
    location_id: Optional[int] = None
    force_refresh: bool = False
    prefer_cached: bool = True


class ResilienceScoreBatchRequest(BaseModel):
    exposure_version_id: int
    hazard_dataset_version_ids: Optional[List[int]] = None
    config: Optional[Dict[str, Any]] = None
    force: bool = False
    policy_pack_version_id: Optional[int] = None


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


class CommitRequest(BaseModel):
    name: Optional[str] = None


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


@router.post("/policy-packs")
def create_policy_pack(
    payload: PolicyPackCreate,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    pack = PolicyPack(
        tenant_id=user.tenant_id,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
    )
    db.add(pack)
    db.commit()
    return {
        "id": pack.id,
        "name": pack.name,
        "description": pack.description,
        "is_active": pack.is_active,
        "created_at": pack.created_at.isoformat(),
    }


@router.post("/policy-packs/{policy_pack_id}/versions")
def create_policy_pack_version(
    policy_pack_id: int,
    payload: PolicyPackVersionCreate,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    pack = db.get(PolicyPack, policy_pack_id)
    if not pack or pack.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy pack not found")
    version = PolicyPackVersion(
        tenant_id=user.tenant_id,
        policy_pack_id=policy_pack_id,
        version_label=payload.version_label,
        scoring_config_json=payload.scoring_config_json,
        underwriting_policy_json=payload.underwriting_policy_json,
    )
    db.add(version)
    db.commit()
    return {
        "id": version.id,
        "policy_pack_id": policy_pack_id,
        "version_label": version.version_label,
        "created_at": version.created_at.isoformat(),
    }


@router.get("/policy-packs")
def list_policy_packs(
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    packs = db.execute(
        select(PolicyPack)
        .where(PolicyPack.tenant_id == user.tenant_id)
        .order_by(PolicyPack.created_at.desc())
    ).scalars().all()
    return {
        "items": [
            {
                "id": pack.id,
                "name": pack.name,
                "description": pack.description,
                "is_active": pack.is_active,
                "created_at": pack.created_at.isoformat(),
                "updated_at": pack.updated_at.isoformat() if pack.updated_at else None,
            }
            for pack in packs
        ]
    }


@router.get("/policy-packs/{policy_pack_id}/versions")
def list_policy_pack_versions(
    policy_pack_id: int,
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    pack = db.get(PolicyPack, policy_pack_id)
    if not pack or pack.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy pack not found")
    versions = db.execute(
        select(PolicyPackVersion)
        .where(
            PolicyPackVersion.tenant_id == user.tenant_id,
            PolicyPackVersion.policy_pack_id == policy_pack_id,
        )
        .order_by(PolicyPackVersion.created_at.desc())
    ).scalars().all()
    return {
        "items": [
            {
                "id": version.id,
                "policy_pack_id": version.policy_pack_id,
                "version_label": version.version_label,
                "created_at": version.created_at.isoformat(),
                "scoring_config_json": version.scoring_config_json,
                "underwriting_policy_json": version.underwriting_policy_json,
            }
            for version in versions
        ]
    }


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
    apply_request_id(run)
    db.add(run)
    db.commit()
    async_result = validate_task.delay(run.id, upload_id, user.tenant_id, run.request_id)
    run.celery_task_id = async_result.id
    db.commit()
    emit_audit(db, user.tenant_id, user.user_id, "validation_requested", {"upload_id": upload_id})
    return {"run_id": run.id, "status": run.status}


@router.get("/validation-results/{validation_result_id}")
def get_validation_result(
    validation_result_id: int,
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
    vr = db.get(ValidationResult, validation_result_id)
    if not vr or vr.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    issues: List[Dict[str, Any]] = []
    if vr.row_errors_uri:
        key = vr.row_errors_uri.split(f"s3://{settings.minio_bucket}/", 1)[1]
        issues = json.loads(get_object(key).decode())
    total = len(issues)
    sliced = issues[offset : offset + limit] if limit else issues[offset:]
    return {
        "id": vr.id,
        "summary": vr.summary_json,
        "issues": sliced,
        "total_issues": total,
        "row_errors_uri": vr.row_errors_uri,
        "checksum": vr.checksum,
        "created_at": vr.created_at.isoformat(),
        "mapping_template_id": vr.mapping_template_id,
        "upload_id": vr.upload_id,
    }


@router.post("/uploads/{upload_id}/commit")
def trigger_commit(
    upload_id: str,
    payload: CommitRequest | None = Body(default=None),
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
    commit_name = payload.name if payload and payload.name else name
    run = Run(
        tenant_id=user.tenant_id,
        run_type=RunType.COMMIT,
        status=RunStatus.QUEUED,
        input_refs_json={"upload_id": upload_id, "name": commit_name or f"Exposure {upload_id}"},
        config_refs_json={"mapping_template_id": upload.mapping_template_id, "idempotency_key": idempotency_key},
        created_by=user.user_id,
        code_version=settings.code_version,
    )
    apply_request_id(run)
    db.add(run)
    db.commit()
    async_result = commit_task.delay(
        run.id,
        upload_id,
        user.tenant_id,
        commit_name or f"Exposure {upload_id}",
        run.request_id,
    )
    run.celery_task_id = async_result.id
    db.commit()
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
    rows = db.execute(
        select(
            ExposureVersion,
            func.count(Location.id).label("location_count"),
            func.sum(Location.tiv).label("tiv_sum"),
        )
        .outerjoin(
            Location,
            and_(
                Location.exposure_version_id == ExposureVersion.id,
                Location.tenant_id == user.tenant_id,
            ),
        )
        .where(ExposureVersion.tenant_id == user.tenant_id)
        .group_by(ExposureVersion.id)
        .order_by(ExposureVersion.created_at.desc())
    ).all()
    return {"items": [
        {
            "id": ev.id,
            "name": ev.name,
            "upload_id": ev.upload_id,
            "created_at": ev.created_at.isoformat(),
            "location_count": location_count or 0,
            "tiv_sum": float(tiv_sum or 0),
        }
        for ev, location_count, tiv_sum in rows
    ]}


@router.get("/exposure-versions/{exposure_version_id}")
def get_exposure_version(exposure_version_id: int, user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    ev = db.get(ExposureVersion, exposure_version_id)
    if not ev or ev.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    location_count = db.execute(
        select(func.count(Location.id)).where(
            Location.exposure_version_id == ev.id,
            Location.tenant_id == user.tenant_id,
        )
    ).scalar_one()
    tiv_sum = db.execute(
        select(func.sum(Location.tiv)).where(
            Location.exposure_version_id == ev.id,
            Location.tenant_id == user.tenant_id,
        )
    ).scalar()
    return {
        "id": ev.id,
        "name": ev.name,
        "upload_id": ev.upload_id,
        "created_at": ev.created_at.isoformat(),
        "location_count": location_count or 0,
        "tiv_sum": float(tiv_sum or 0),
    }


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
            "location_id": r.id,
            "external_location_id": r.external_location_id,
            "address_line1": r.address_line1,
            "city": r.city,
            "state_region": r.state_region,
            "postal_code": r.postal_code,
            "country": r.country,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "tiv": r.tiv,
        }
        for r in rows
    ]}


@router.patch("/locations/{location_id}/structural")
def update_location_structural(
    location_id: int,
    payload: LocationStructuralRequest,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    location = db.get(Location, location_id)
    if not location or location.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    merged = merge_structural(location.structural_json, payload.structural)
    location.structural_json = merged
    location.updated_at = datetime.utcnow()
    db.commit()
    emit_audit(
        db,
        user.tenant_id,
        user.user_id,
        "location_structural_updated",
        {"location_id": location.id, "external_location_id": location.external_location_id},
    )
    return {"location_id": location.id, "structural_json": merged}


@router.post("/exposure-versions/{exposure_version_id}/structural")
def batch_update_structural(
    exposure_version_id: int,
    payload: ExposureStructuralBatchRequest,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ev = db.get(ExposureVersion, exposure_version_id)
    if not ev or ev.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    updated = 0
    not_found = 0
    skipped_invalid = 0
    for item in payload.items:
        normalized_override = normalize_structural(item.structural)
        if not normalized_override:
            skipped_invalid += 1
            continue
        loc = db.execute(
            select(Location).where(
                Location.tenant_id == user.tenant_id,
                Location.exposure_version_id == exposure_version_id,
                Location.external_location_id == item.external_location_id,
            )
        ).scalar_one_or_none()
        if not loc:
            not_found += 1
            continue
        loc.structural_json = merge_structural(loc.structural_json, normalized_override)
        loc.updated_at = datetime.utcnow()
        updated += 1
    db.commit()
    return {"updated": updated, "not_found": not_found, "skipped_invalid": skipped_invalid}


@router.post("/property-profiles/resolve")
def resolve_property_profile(
    payload: PropertyProfileResolveRequest,
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    normalized = normalize_address(payload.address)
    fingerprint = address_fingerprint(normalized)
    existing = db.execute(
        select(PropertyProfile).where(
            PropertyProfile.tenant_id == user.tenant_id,
            PropertyProfile.address_fingerprint == fingerprint,
        )
    ).scalar_one_or_none()
    if existing and payload.prefer_cached and not payload.force_refresh and is_profile_fresh(existing.updated_at):
        return {
            "run_id": None,
            "property_profile_id": existing.id,
            "status": "CACHED",
        }

    existing_run = db.execute(
        select(Run).where(
            Run.tenant_id == user.tenant_id,
            Run.run_type == RunType.PROPERTY_ENRICHMENT,
            Run.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]),
            Run.input_refs_json["address_fingerprint"].astext == fingerprint,
        )
    ).scalar_one_or_none()
    if existing_run:
        return {
            "run_id": existing_run.id,
            "property_profile_id": existing.id if existing else None,
            "status": "EXISTING_IN_PROGRESS",
        }

    run = Run(
        tenant_id=user.tenant_id,
        run_type=RunType.PROPERTY_ENRICHMENT,
        status=RunStatus.QUEUED,
        input_refs_json={
            "address_fingerprint": fingerprint,
            "location_id": payload.location_id,
            "address": payload.address,
        },
        created_by=user.user_id,
        code_version=settings.code_version,
    )
    apply_request_id(run)
    db.add(run)
    db.commit()
    async_result = enrich_property_profile_task.delay(
        run.id,
        user.tenant_id,
        payload.address,
        payload.location_id,
        payload.force_refresh,
        run.request_id,
    )
    run.celery_task_id = async_result.id
    db.commit()
    return {
        "run_id": run.id,
        "property_profile_id": existing.id if existing else None,
        "status": "QUEUED",
    }


@router.get("/property-profiles/{property_profile_id}")
def get_property_profile(
    property_profile_id: int,
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    profile = db.get(PropertyProfile, property_profile_id)
    if not profile or profile.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return {
        "id": profile.id,
        "location_id": profile.location_id,
        "address_fingerprint": profile.address_fingerprint,
        "standardized_address_json": profile.standardized_address_json,
        "geocode_json": profile.geocode_json,
        "parcel_json": profile.parcel_json,
        "characteristics_json": profile.characteristics_json,
        "structural_json": profile.structural_json,
        "provenance_json": profile.provenance_json,
        "code_version": profile.code_version,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


@router.get("/property-profiles/runs/{run_id}/status")
def get_property_profile_run_status(
    run_id: int,
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    run = db.get(Run, run_id)
    if not run or run.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    status_value = run.status.value if hasattr(run.status, "value") else run.status
    progress = extract_progress(run.output_refs_json)
    return {
        "run_id": run.id,
        "status": status_value,
        "output_refs": run.output_refs_json,
        "request_id": run.request_id,
        "celery_task_id": run.celery_task_id,
        "progress": progress,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.completed_at.isoformat() if run.completed_at else None,
        "cancelled_at": run.cancelled_at.isoformat() if run.cancelled_at else None,
    }


@router.post("/runs/{run_id}/cancel")
def cancel_run(
    run_id: int,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    run = db.get(Run, run_id)
    if not run or run.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    status_value = run.status.value if hasattr(run.status, "value") else run.status
    if status_value in (RunStatus.QUEUED.value, RunStatus.RUNNING.value, RunStatus.QUEUED, RunStatus.RUNNING):
        run.status = RunStatus.CANCELLED
        run.cancelled_at = datetime.utcnow()
        run.completed_at = datetime.utcnow()
        db.commit()
        if run.celery_task_id:
            try:
                celery_app.control.revoke(run.celery_task_id, terminate=False)
            except Exception:
                pass
        status_value = RunStatus.CANCELLED.value
    return {
        "run_id": run.id,
        "status": status_value,
        "request_id": run.request_id,
        "celery_task_id": run.celery_task_id,
        "cancelled_at": run.cancelled_at.isoformat() if run.cancelled_at else None,
    }


@router.post("/runs/{run_id}/retry")
def retry_run(
    run_id: int,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    run = db.get(Run, run_id)
    if not run or run.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    status_value = run.status.value if hasattr(run.status, "value") else run.status
    if status_value not in (RunStatus.FAILED.value, RunStatus.CANCELLED.value, RunStatus.FAILED, RunStatus.CANCELLED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run is not retryable")

    new_run = Run(
        tenant_id=user.tenant_id,
        run_type=run.run_type,
        status=RunStatus.QUEUED,
        input_refs_json=run.input_refs_json,
        config_refs_json=run.config_refs_json,
        created_by=user.user_id,
        code_version=settings.code_version,
    )
    apply_request_id(new_run)
    db.add(new_run)
    db.commit()

    response: Dict[str, Any] = {"run_id": new_run.id, "status": new_run.status}
    if run.run_type == RunType.RESILIENCE_SCORE:
        result = db.execute(
            select(ResilienceScoreResult).where(ResilienceScoreResult.run_id == run.id)
        ).scalar_one_or_none()
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resilience score result not found")
        db.query(ResilienceScoreItem).filter(
            ResilienceScoreItem.tenant_id == user.tenant_id,
            ResilienceScoreItem.resilience_score_result_id == result.id,
        ).delete(synchronize_session=False)
        result.run_id = new_run.id
        db.commit()
        async_result = resilience_score_task.delay(
            new_run.id,
            result.id,
            result.exposure_version_id,
            result.hazard_dataset_version_ids_json or [],
            user.tenant_id,
            result.scoring_config_json,
            new_run.request_id,
        )
        new_run.celery_task_id = async_result.id
        db.commit()
        response.update({"resilience_score_result_id": result.id})
    elif run.run_type == RunType.PROPERTY_ENRICHMENT:
        address = (run.input_refs_json or {}).get("address")
        if not address:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing address for retry")
        location_id = (run.input_refs_json or {}).get("location_id")
        async_result = enrich_property_profile_task.delay(
            new_run.id,
            user.tenant_id,
            address,
            location_id,
            True,
            new_run.request_id,
        )
        new_run.celery_task_id = async_result.id
        db.commit()
        fingerprint = (run.input_refs_json or {}).get("address_fingerprint")
        if not fingerprint:
            fingerprint = address_fingerprint(normalize_address(address))
        profile = db.execute(
            select(PropertyProfile).where(
                PropertyProfile.tenant_id == user.tenant_id,
                PropertyProfile.address_fingerprint == fingerprint,
            )
        ).scalar_one_or_none()
        response.update({"property_profile_id": profile.id if profile else None})
    elif run.run_type == RunType.VALIDATION:
        upload_id = (run.input_refs_json or {}).get("upload_id")
        if not upload_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing upload_id for retry")
        async_result = validate_task.delay(new_run.id, upload_id, user.tenant_id, new_run.request_id)
        new_run.celery_task_id = async_result.id
        db.commit()
    elif run.run_type == RunType.COMMIT:
        upload_id = (run.input_refs_json or {}).get("upload_id")
        if not upload_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing upload_id for retry")
        name = (run.input_refs_json or {}).get("name") or f"Exposure {upload_id}"
        async_result = commit_task.delay(new_run.id, upload_id, user.tenant_id, name, new_run.request_id)
        new_run.celery_task_id = async_result.id
        db.commit()
    elif run.run_type == RunType.GEOCODE:
        exposure_version_id = (run.input_refs_json or {}).get("exposure_version_id")
        if exposure_version_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing exposure_version_id for retry")
        async_result = geocode_task.delay(new_run.id, exposure_version_id, user.tenant_id, new_run.request_id)
        new_run.celery_task_id = async_result.id
        db.commit()
    elif run.run_type == RunType.OVERLAY:
        overlay = db.execute(
            select(HazardOverlayResult).where(HazardOverlayResult.run_id == run.id)
        ).scalar_one_or_none()
        if not overlay:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hazard overlay result not found")
        db.query(LocationHazardAttribute).filter(
            LocationHazardAttribute.tenant_id == user.tenant_id,
            LocationHazardAttribute.hazard_overlay_result_id == overlay.id,
        ).delete(synchronize_session=False)
        overlay.run_id = new_run.id
        db.commit()
        params = (run.config_refs_json or {}).get("params")
        async_result = overlay_task.delay(
            new_run.id,
            overlay.id,
            overlay.exposure_version_id,
            overlay.hazard_dataset_version_id,
            user.tenant_id,
            params,
            new_run.request_id,
        )
        new_run.celery_task_id = async_result.id
        db.commit()
        response.update({"overlay_result_id": overlay.id})
    elif run.run_type == RunType.ROLLUP:
        rollup_result = db.execute(
            select(RollupResult).where(RollupResult.run_id == run.id)
        ).scalar_one_or_none()
        if not rollup_result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rollup result not found")
        db.query(RollupResultItem).filter(
            RollupResultItem.tenant_id == user.tenant_id,
            RollupResultItem.rollup_result_id == rollup_result.id,
        ).delete(synchronize_session=False)
        rollup_result.run_id = new_run.id
        db.commit()
        async_result = rollup_task.delay(
            new_run.id,
            rollup_result.id,
            rollup_result.exposure_version_id,
            rollup_result.rollup_config_id,
            rollup_result.hazard_overlay_result_ids_json or [],
            user.tenant_id,
            new_run.request_id,
        )
        new_run.celery_task_id = async_result.id
        db.commit()
        response.update({"rollup_result_id": rollup_result.id})
    elif run.run_type == RunType.BREACH_EVAL:
        rollup_result_id = (run.input_refs_json or {}).get("rollup_result_id")
        threshold_rule_ids = (run.config_refs_json or {}).get("threshold_rule_ids")
        if rollup_result_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing rollup_result_id for retry")
        async_result = breach_task.delay(
            new_run.id,
            rollup_result_id,
            threshold_rule_ids,
            user.tenant_id,
            new_run.request_id,
        )
        new_run.celery_task_id = async_result.id
        db.commit()
    elif run.run_type == RunType.DRIFT:
        drift_run = db.execute(
            select(DriftRun).where(DriftRun.run_id == run.id)
        ).scalar_one_or_none()
        if not drift_run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drift run not found")
        db.query(DriftDetail).filter(
            DriftDetail.tenant_id == user.tenant_id,
            DriftDetail.drift_run_id == drift_run.id,
        ).delete(synchronize_session=False)
        drift_run.run_id = new_run.id
        db.commit()
        async_result = drift_task.delay(
            new_run.id,
            drift_run.id,
            drift_run.exposure_version_a_id,
            drift_run.exposure_version_b_id,
            user.tenant_id,
            new_run.request_id,
        )
        new_run.celery_task_id = async_result.id
        db.commit()
        response.update({"drift_run_id": drift_run.id})
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported run type")

    return response


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
    apply_request_id(run)
    db.add(run)
    db.commit()
    async_result = geocode_task.delay(run.id, exposure_version_id, user.tenant_id, run.request_id)
    run.celery_task_id = async_result.id
    db.commit()
    emit_audit(db, user.tenant_id, user.user_id, "geocode_requested", {"exposure_version_id": exposure_version_id})
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
    emit_audit(db, user.tenant_id, user.user_id, "hazard_dataset_created", {"hazard_dataset_id": dataset.id})
    return {
        "id": dataset.id,
        "name": dataset.name,
        "peril": dataset.peril,
        "vendor": dataset.vendor,
        "coverage_geo": dataset.coverage_geo,
        "license_ref": dataset.license_ref,
        "created_at": dataset.created_at.isoformat(),
    }


@router.get("/hazard-datasets")
def list_hazard_datasets(user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    rows = db.execute(
        select(HazardDataset)
        .where(HazardDataset.tenant_id == user.tenant_id)
        .order_by(HazardDataset.created_at.desc())
    ).scalars().all()
    return {"items": [
        {
            "id": r.id,
            "name": r.name,
            "peril": r.peril,
            "vendor": r.vendor,
            "coverage_geo": r.coverage_geo,
            "license_ref": r.license_ref,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]}


@router.post("/hazard-datasets/{hazard_dataset_id}/versions")
def upload_hazard_dataset_version(
    hazard_dataset_id: int,
    version_label: Optional[str] = None,
    file: UploadFile = File(...),
    effective_date: Optional[str] = None,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    dataset = db.get(HazardDataset, hazard_dataset_id)
    if not dataset or dataset.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    payload = file.file.read()
    checksum = compute_checksum(payload)
    label = version_label or f"v{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    key = f"hazards/{user.tenant_id}/{hazard_dataset_id}/{label}/{file.filename}"
    uri = put_object(key, payload, content_type=file.content_type or "application/json")
    eff = datetime.fromisoformat(effective_date) if effective_date else None
    version = HazardDatasetVersion(
        tenant_id=user.tenant_id,
        hazard_dataset_id=hazard_dataset_id,
        version_label=label,
        storage_uri=uri,
        checksum=checksum,
        effective_date=eff,
    )
    db.add(version)
    db.commit()
    try:
        geojson = json.loads(payload.decode())
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid GeoJSON") from exc
    features = geojson.get("features") or []
    rows = []
    for feature in features:
        geom = feature.get("geometry")
        if not geom:
            continue
        geom_json = json.dumps(geom)
        rows.append(
            HazardFeaturePolygon(
                tenant_id=user.tenant_id,
                hazard_dataset_version_id=version.id,
                geom=func.ST_Multi(func.ST_SetSRID(func.ST_GeomFromGeoJSON(geom_json), 4326)),
                properties_json=feature.get("properties") or {},
            )
        )
    if rows:
        db.add_all(rows)
        db.commit()
    emit_audit(db, user.tenant_id, user.user_id, "hazard_dataset_version_created", {"hazard_dataset_version_id": version.id})
    return {
        "id": version.id,
        "version_label": version.version_label,
        "checksum": version.checksum,
        "created_at": version.created_at.isoformat(),
        "effective_date": version.effective_date.isoformat() if version.effective_date else None,
    }


@router.get("/hazard-datasets/{hazard_dataset_id}/versions")
def list_hazard_dataset_versions(hazard_dataset_id: int, user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    dataset = db.get(HazardDataset, hazard_dataset_id)
    if not dataset or dataset.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    rows = db.execute(
        select(HazardDatasetVersion)
        .where(
            HazardDatasetVersion.tenant_id == user.tenant_id,
            HazardDatasetVersion.hazard_dataset_id == hazard_dataset_id,
        )
        .order_by(HazardDatasetVersion.created_at.desc())
    ).scalars().all()
    return {"items": [
        {
            "id": r.id,
            "version_label": r.version_label,
            "checksum": r.checksum,
            "created_at": r.created_at.isoformat(),
            "effective_date": r.effective_date.isoformat() if r.effective_date else None,
        }
        for r in rows
    ]}


@router.post("/resilience/score")
def score_resilience(
    payload: ResilienceScoreRequest,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    lat = payload.lat
    lon = payload.lon
    geocode_method = None
    geocode_confidence = None
    structural_override = payload.structural.dict() if payload.structural else None
    structural_used: Dict[str, Any] = {}
    property_profile: Optional[PropertyProfile] = None
    property_profile_id = None
    property_profile_updated_at = None
    property_enriched = False
    structural_source = "payload"
    hazard_versions_used = []
    enrichment_status = "skipped"
    enrichment_waited_seconds = 0
    enrichment_errors: List[Dict[str, Any]] = []
    enrichment_failed = False
    enrichment_attempted = False
    try:
        scoring_config, _, policy_meta = resolve_policy_version(
            db, user.tenant_id, payload.policy_pack_version_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if payload.location_id is not None:
        location = db.get(Location, payload.location_id)
        if not location or location.tenant_id != user.tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
        lat = location.latitude
        lon = location.longitude
        if lat is None or lon is None:
            if not (location.address_line1 and location.city and location.country):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="location_id missing coordinates and address",
                )
            lat, lon, geocode_confidence, geocode_method = geocode_address(
                location.address_line1,
                location.city,
                location.country,
                postal_code=location.postal_code or "",
                state_region=location.state_region or "",
            )
        else:
            geocode_method = "PROVIDED"
            geocode_confidence = 1.0
        structural_used = merge_structural(location.structural_json, structural_override)
        structural_source = "location"
        if structural_override and normalize_structural(structural_override):
            structural_source = "mixed"
        enrichment_status = "skipped"
    else:
        address_json = {
            "address_line1": payload.address_line1,
            "city": payload.city,
            "state_region": payload.state_region,
            "postal_code": payload.postal_code,
            "country": payload.country,
        }
        address_present = payload.address_line1 and payload.city and payload.country
        if address_present:
            normalized_address = normalize_address(address_json)
            fingerprint = address_fingerprint(normalized_address)
            profile = db.execute(
                select(PropertyProfile).where(
                    PropertyProfile.tenant_id == user.tenant_id,
                    PropertyProfile.address_fingerprint == fingerprint,
                )
            ).scalar_one_or_none()
            if profile:
                property_profile = profile
                property_profile_id = profile.id
                property_profile_updated_at = profile.updated_at.isoformat() if profile.updated_at else None
                property_enriched = True
                if lat is None or lon is None:
                    geocode = profile.geocode_json or {}
                    lat = geocode.get("lat")
                    lon = geocode.get("lon")
                    geocode_method = geocode.get("method")
                    geocode_confidence = geocode.get("confidence")
                structural_used = merge_structural(profile.structural_json, structural_override)
                structural_source = "profile"
                if structural_override and normalize_structural(structural_override):
                    structural_source = "mixed"
                enrichment_status = "used_profile"
                enrichment_errors = (profile.provenance_json or {}).get("errors") or []
            else:
                enrichment_attempted = True
                if not payload.enrich:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Property enrichment disabled and no profile exists",
                    )
                mode = determine_enrich_mode(payload.enrich_mode, providers_are_stub())
                if mode == "async":
                    run = Run(
                        tenant_id=user.tenant_id,
                        run_type=RunType.PROPERTY_ENRICHMENT,
                        status=RunStatus.QUEUED,
                        input_refs_json={"address_fingerprint": fingerprint, "address": address_json},
                        created_by=user.user_id,
                        code_version=settings.code_version,
                    )
                    apply_request_id(run)
                    db.add(run)
                    db.commit()
                    async_result = enrich_property_profile_task.delay(
                        run.id,
                        user.tenant_id,
                        address_json,
                        None,
                        False,
                        run.request_id,
                    )
                    run.celery_task_id = async_result.id
                    db.commit()
                    wait_seconds = payload.wait_for_enrichment_seconds or 0
                    run_status = None
                    if wait_seconds > 0:
                        start = time.monotonic()
                        while time.monotonic() - start < wait_seconds:
                            polled = db.get(Run, run.id)
                            if polled:
                                run_status = polled.status.value if hasattr(polled.status, "value") else polled.status
                            if run_status in ("SUCCEEDED", "FAILED"):
                                break
                            time.sleep(0.25)
                        enrichment_waited_seconds = int(round(time.monotonic() - start))
                        if run_status == "SUCCEEDED":
                            profile = db.execute(
                                select(PropertyProfile).where(
                                    PropertyProfile.tenant_id == user.tenant_id,
                                    PropertyProfile.address_fingerprint == fingerprint,
                                )
                            ).scalar_one_or_none()
                            if profile:
                                property_profile = profile
                                property_profile_id = profile.id
                                property_profile_updated_at = profile.updated_at.isoformat() if profile.updated_at else None
                                property_enriched = True
                                if lat is None or lon is None:
                                    geocode = profile.geocode_json or {}
                                    lat = geocode.get("lat")
                                    lon = geocode.get("lon")
                                    geocode_method = geocode.get("method")
                                    geocode_confidence = geocode.get("confidence")
                                structural_used = merge_structural(profile.structural_json, structural_override)
                                structural_source = "profile"
                                if structural_override and normalize_structural(structural_override):
                                    structural_source = "mixed"
                                enrichment_status = "used_profile"
                                enrichment_errors = (profile.provenance_json or {}).get("errors") or []
                            else:
                                enrichment_failed = True
                                enrichment_status = "failed"
                        elif run_status == "FAILED":
                            enrichment_failed = True
                            enrichment_status = "failed"

                    decision = decide_enrichment_action(
                        async_required=True,
                        wait_seconds=wait_seconds,
                        best_effort=payload.best_effort,
                        run_status=run_status,
                    )
                    if decision["action"] == "return_202":
                        return JSONResponse(
                            status_code=status.HTTP_202_ACCEPTED,
                            content={
                                "status": "ENRICHMENT_QUEUED",
                                "run_id": run.id,
                                "address_fingerprint": fingerprint,
                                "message": "Enrichment queued. Retry /resilience/score with the same address or call GET /property-profiles/runs/{run_id}/status.",
                            },
                        )
                    if decision["action"] == "error":
                        return JSONResponse(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            content={"detail": "Enrichment failed", "errors": enrichment_errors},
                        )
                    if decision["enrichment_failed"]:
                        enrichment_failed = True
                        enrichment_status = decision["enrichment_status"]
                    if not property_profile:
                        structural_used = normalize_structural(structural_override)
                        structural_source = "payload"
                        if not enrichment_failed:
                            enrichment_status = decision["enrichment_status"]
                else:
                    payload_profile = run_enrichment_pipeline(address_json)
                    profile = PropertyProfile(
                        tenant_id=user.tenant_id,
                        address_fingerprint=payload_profile["address_fingerprint"],
                        standardized_address_json=payload_profile["standardized_address_json"],
                        geocode_json=payload_profile["geocode_json"],
                        parcel_json=payload_profile["parcel_json"],
                        characteristics_json=payload_profile["characteristics_json"],
                        structural_json=payload_profile["structural_json"],
                        provenance_json=payload_profile["provenance_json"],
                        code_version=payload_profile["code_version"],
                    )
                    db.add(profile)
                    db.commit()
                    property_profile = profile
                    property_profile_id = profile.id
                    property_profile_updated_at = profile.updated_at.isoformat() if profile.updated_at else None
                    property_enriched = True
                    if lat is None or lon is None:
                        geocode = profile.geocode_json or {}
                        lat = geocode.get("lat")
                        lon = geocode.get("lon")
                        geocode_method = geocode.get("method")
                        geocode_confidence = geocode.get("confidence")
                    structural_used = merge_structural(profile.structural_json, structural_override)
                    structural_source = "profile"
                    if structural_override and normalize_structural(structural_override):
                        structural_source = "mixed"
                    enrichment_status = "used_profile"
                    enrichment_errors = (profile.provenance_json or {}).get("errors") or []
        else:
            if lat is None or lon is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="lat/lon or address_line1, city, country required",
                )
            geocode_method = "PROVIDED"
            geocode_confidence = 1.0
            structural_used = normalize_structural(structural_override)
            enrichment_status = "skipped"

    if lat is not None and lon is not None and geocode_method is None:
        geocode_method = "PROVIDED"
        geocode_confidence = 1.0

    if lat is None or lon is None:
        if enrichment_attempted and not payload.best_effort:
            return JSONResponse(
                status_code=status.HTTP_502_BAD_GATEWAY,
                content={"detail": "Enrichment failed", "errors": enrichment_errors},
            )
        if not payload.best_effort:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to resolve coordinates for scoring")
        enrichment_failed = True

    version_ids: List[int] = []
    if payload.hazard_dataset_version_ids is not None:
        requested_ids = payload.hazard_dataset_version_ids
        if requested_ids:
            version_ids = db.execute(
                select(HazardDatasetVersion.id).where(
                    HazardDatasetVersion.tenant_id == user.tenant_id,
                    HazardDatasetVersion.id.in_(requested_ids),
                )
            ).scalars().all()
            if not version_ids:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hazard dataset versions not found")
    else:
        datasets = db.execute(
            select(HazardDataset).where(HazardDataset.tenant_id == user.tenant_id)
        ).scalars().all()
        for dataset in datasets:
            latest = db.execute(
                select(HazardDatasetVersion.id)
                .where(
                    HazardDatasetVersion.tenant_id == user.tenant_id,
                    HazardDatasetVersion.hazard_dataset_id == dataset.id,
                )
                .order_by(
                    HazardDatasetVersion.effective_date.desc().nullslast(),
                    HazardDatasetVersion.created_at.desc(),
                )
                .limit(1)
            ).scalar_one_or_none()
            if latest:
                version_ids.append(latest)

    hazard_versions_used = build_hazard_versions(db, user.tenant_id, version_ids)
    hazards: Dict[str, Dict[str, Any]] = {}
    if version_ids and lat is not None and lon is not None:
        point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
        rows = db.execute(
            select(HazardFeaturePolygon, HazardDatasetVersion, HazardDataset)
            .join(HazardDatasetVersion, HazardFeaturePolygon.hazard_dataset_version_id == HazardDatasetVersion.id)
            .join(HazardDataset, HazardDatasetVersion.hazard_dataset_id == HazardDataset.id)
            .where(
                HazardFeaturePolygon.tenant_id == user.tenant_id,
                HazardDatasetVersion.tenant_id == user.tenant_id,
                HazardDataset.tenant_id == user.tenant_id,
                HazardFeaturePolygon.hazard_dataset_version_id.in_(version_ids),
                func.ST_Contains(HazardFeaturePolygon.geom, point),
            )
        ).all()
        for feature, version, dataset in rows:
            entry = extract_hazard_entry(
                feature.properties_json or {},
                dataset.peril,
                dataset.name,
                version.version_label,
            )
            merge_worst_in_peril(hazards, entry)

    result = compute_resilience_score(hazards, structural_used, scoring_config)
    hazard_response = {
        peril: {"score": data.get("score"), "band": data.get("band"), "source": data.get("source")}
        for peril, data in hazards.items()
    }
    perils = list(DEFAULT_WEIGHTS.keys())
    peril_present = []
    peril_missing = []
    for peril in perils:
        score_value = hazards.get(peril, {}).get("score") if hazards.get(peril) else None
        if isinstance(score_value, (int, float)):
            peril_present.append(peril)
        else:
            peril_missing.append(peril)
    used_unknown_hazard_fallback = len(peril_missing) > 0

    data_quality = {
        "peril_present": peril_present,
        "peril_missing": peril_missing,
        "used_unknown_hazard_fallback": used_unknown_hazard_fallback,
        "property_enriched": property_enriched,
        "structural_source": structural_source,
        "enrichment_profile_id": property_profile_id,
        "enrichment_status": enrichment_status,
        "enrichment_waited_seconds": enrichment_waited_seconds,
        "enrichment_errors": enrichment_errors,
        "enrichment_failed": enrichment_failed,
        "best_effort": payload.best_effort,
        "completeness": compute_structural_completeness(structural_used),
    }
    explainability = build_explainability(result, hazard_response, structural_used, None, data_quality)

    return {
        "location": {
            "lat": lat,
            "lon": lon,
            "geocode_method": geocode_method,
            "geocode_confidence": geocode_confidence,
        },
        "hazards": hazard_response,
        "structural": structural_used,
        "hazard_versions_used": hazard_versions_used,
        "scoring_version": SCORING_VERSION,
        "code_version": settings.code_version,
        "policy_used": policy_meta,
        "property_profile_id": property_profile_id,
        "property_profile_updated_at": property_profile_updated_at,
        "property_profile": summarize_property_profile(property_profile),
        "data_quality": data_quality,
        "explainability": explainability,
        "result": result,
    }


@router.post("/underwriting/packet")
def underwriting_packet(
    payload: ResilienceScoreRequest,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    response = score_resilience(payload, user, db)
    if isinstance(response, JSONResponse):
        return response
    try:
        _, underwriting_policy, policy_meta = resolve_policy_version(
            db, user.tenant_id, payload.policy_pack_version_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    underwriting_policy = merge_policy_overrides(underwriting_policy, payload.underwriting_policy or {})
    property_summary = response.get("property_profile")
    if not property_summary:
        property_summary = {
            "location": response.get("location"),
            "structural_json": response.get("structural"),
        }
    decision_payload = None
    if payload.include_decision:
        decision_payload = evaluate_underwriting_decision(
            response.get("result") or {},
            response.get("hazards") or {},
            response.get("structural") or {},
            response.get("data_quality") or {},
            policy=underwriting_policy,
        )
    explainability = build_explainability(
        response.get("result") or {},
        response.get("hazards") or {},
        response.get("structural") or {},
        decision_payload,
        response.get("data_quality") or {},
    )
    return {
        "property": property_summary,
        "hazards": response.get("hazards"),
        "resilience": response.get("result"),
        "provenance": {
            "scoring_version": response.get("scoring_version"),
            "code_version": response.get("code_version"),
            "hazard_versions_used": response.get("hazard_versions_used"),
        },
        "quality": response.get("data_quality"),
        "decision": decision_payload,
        "explainability": explainability,
        "policy_used": policy_meta,
    }


@router.get("/resilience-scores")
def list_resilience_scores(
    exposure_version_id: int,
    limit: int = 20,
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    limit = min(max(limit, 1), 100)
    rows = db.execute(
        select(ResilienceScoreResult, Run)
        .outerjoin(Run, ResilienceScoreResult.run_id == Run.id)
        .where(
            ResilienceScoreResult.tenant_id == user.tenant_id,
            ResilienceScoreResult.exposure_version_id == exposure_version_id,
        )
        .order_by(ResilienceScoreResult.created_at.desc())
        .limit(limit)
    ).all()
    items = []
    for result, run in rows:
        status_value = run.status.value if run and hasattr(run.status, "value") else (run.status if run else None)
        items.append(
            {
                "id": result.id,
                "created_at": result.created_at.isoformat() if result.created_at else None,
                "scoring_version": result.scoring_version,
                "code_version": result.code_version,
                "hazard_versions_used": result.hazard_versions_json,
                "policy_used": result.policy_used_json or {"policy_pack_version_id": None, "version_label": "default"},
                "policy_pack_version_id": result.policy_pack_version_id,
                "status": status_value,
                "run_id": result.run_id,
            }
        )
    return {"items": items, "limit": limit}


@router.post("/resilience-scores")
def create_resilience_scores(
    payload: ResilienceScoreBatchRequest,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    exposure_version = db.get(ExposureVersion, payload.exposure_version_id)
    if not exposure_version or exposure_version.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exposure version not found")

    version_ids: List[int] = []
    if payload.hazard_dataset_version_ids is not None:
        requested_ids = payload.hazard_dataset_version_ids
        if requested_ids:
            version_ids = db.execute(
                select(HazardDatasetVersion.id).where(
                    HazardDatasetVersion.tenant_id == user.tenant_id,
                    HazardDatasetVersion.id.in_(requested_ids),
                )
            ).scalars().all()
            if not version_ids:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hazard dataset versions not found")
    else:
        datasets = db.execute(
            select(HazardDataset).where(HazardDataset.tenant_id == user.tenant_id)
        ).scalars().all()
        for dataset in datasets:
            latest = db.execute(
                select(HazardDatasetVersion.id)
                .where(
                    HazardDatasetVersion.tenant_id == user.tenant_id,
                    HazardDatasetVersion.hazard_dataset_id == dataset.id,
                )
                .order_by(
                    HazardDatasetVersion.effective_date.desc().nullslast(),
                    HazardDatasetVersion.created_at.desc(),
                )
                .limit(1)
            ).scalar_one_or_none()
            if latest:
                version_ids.append(latest)

    version_ids = sorted(version_ids)
    hazard_versions_used = build_hazard_versions(db, user.tenant_id, version_ids)
    try:
        scoring_config, _, policy_meta = resolve_policy_version(
            db, user.tenant_id, payload.policy_pack_version_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    scoring_config_used = merge_policy_overrides(scoring_config, payload.config or {})

    request_payload = {
        "tenant_id": user.tenant_id,
        "exposure_version_id": payload.exposure_version_id,
        "hazard_dataset_version_ids": version_ids,
        "config": scoring_config_used,
        "scoring_version": SCORING_VERSION,
        "code_version": settings.code_version,
        "policy_pack_version_id": payload.policy_pack_version_id,
    }
    base_fingerprint = fingerprint_resilience_scores_request(
        user.tenant_id,
        payload.exposure_version_id,
        version_ids,
        scoring_config_used,
        SCORING_VERSION,
        settings.code_version,
        payload.policy_pack_version_id,
    )
    request_json = dict(request_payload)
    now = datetime.utcnow()
    cutoff = now - timedelta(days=30)

    if not payload.force:
        existing = db.execute(
            select(ResilienceScoreResult).where(
                ResilienceScoreResult.tenant_id == user.tenant_id,
                ResilienceScoreResult.request_fingerprint == base_fingerprint,
            )
        ).scalar_one_or_none()
        if existing:
            existing_run = db.get(Run, existing.run_id) if existing.run_id else None
            existing_status = (
                existing_run.status.value if existing_run and hasattr(existing_run.status, "value") else existing_run.status
            )
            if existing_run is None:
                request_json["rerun_at"] = now.isoformat()
            if existing_status in (RunStatus.QUEUED.value, RunStatus.RUNNING.value, RunStatus.QUEUED, RunStatus.RUNNING):
                return {
                    "resilience_score_result_id": existing.id,
                    "run_id": existing.run_id,
                    "status": "EXISTING_IN_PROGRESS",
                }
            if existing_status in (RunStatus.SUCCEEDED.value, RunStatus.SUCCEEDED) and (
                existing.created_at and existing.created_at >= cutoff
            ):
                return {
                    "resilience_score_result_id": existing.id,
                    "run_id": existing.run_id,
                    "status": "EXISTING_SUCCEEDED",
                }
            if existing_status in (RunStatus.FAILED.value, RunStatus.FAILED) or (
                existing.created_at and existing.created_at < cutoff
            ):
                request_json["rerun_at"] = now.isoformat()

    if payload.force:
        request_json["forced_at"] = now.isoformat()

    request_fingerprint = base_fingerprint
    if request_json.get("forced_at") or request_json.get("rerun_at"):
        request_fingerprint = hashlib.sha256(canonical_json(request_json).encode()).hexdigest()
    run = Run(
        tenant_id=user.tenant_id,
        run_type=RunType.RESILIENCE_SCORE,
        status=RunStatus.QUEUED,
        input_refs_json={
            "exposure_version_id": payload.exposure_version_id,
            "hazard_dataset_version_ids": version_ids,
            "policy_pack_version_id": payload.policy_pack_version_id,
        },
        config_refs_json={"config": scoring_config_used, "policy_pack_version_id": payload.policy_pack_version_id},
        created_by=user.user_id,
        code_version=settings.code_version,
    )
    apply_request_id(run)
    db.add(run)
    db.commit()

    result = ResilienceScoreResult(
        tenant_id=user.tenant_id,
        exposure_version_id=payload.exposure_version_id,
        run_id=run.id,
        scoring_version=SCORING_VERSION,
        code_version=settings.code_version,
        hazard_dataset_version_ids_json=version_ids,
        hazard_versions_json=hazard_versions_used,
        scoring_config_json=scoring_config_used,
        policy_pack_version_id=payload.policy_pack_version_id,
        policy_used_json=policy_meta,
        request_fingerprint=request_fingerprint,
        request_json=request_json,
    )
    db.add(result)
    try:
        db.commit()
    except Exception:
        db.rollback()
        if not payload.force:
            existing = db.execute(
                select(ResilienceScoreResult).where(
                    ResilienceScoreResult.tenant_id == user.tenant_id,
                    ResilienceScoreResult.request_fingerprint == request_fingerprint,
                )
            ).scalar_one_or_none()
            if existing:
                return {
                    "resilience_score_result_id": existing.id,
                    "run_id": existing.run_id,
                    "status": "EXISTING_IN_PROGRESS",
                }
        raise

    async_result = resilience_score_task.delay(
        run.id,
        result.id,
        payload.exposure_version_id,
        version_ids,
        user.tenant_id,
        scoring_config_used,
        run.request_id,
    )
    run.celery_task_id = async_result.id
    db.commit()
    emit_audit(db, user.tenant_id, user.user_id, "resilience_scores_requested", {"resilience_score_result_id": result.id})
    return {"resilience_score_result_id": result.id, "run_id": run.id, "status": "QUEUED"}


@router.get("/resilience-scores/{resilience_score_result_id}/status")
def get_resilience_score_status(
    resilience_score_result_id: int,
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    result = db.get(ResilienceScoreResult, resilience_score_result_id)
    if not result or result.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    run = db.get(Run, result.run_id) if result.run_id else None
    status_value = run.status.value if run and hasattr(run.status, "value") else (run.status if run else "PENDING")
    progress = extract_progress(run.output_refs_json) if run else None
    return {
        "resilience_score_result_id": result.id,
        "status": status_value,
        "run_id": result.run_id,
        "request_id": run.request_id if run else None,
        "celery_task_id": run.celery_task_id if run else None,
        "progress": progress,
        "started_at": run.started_at.isoformat() if run and run.started_at else None,
        "finished_at": run.completed_at.isoformat() if run and run.completed_at else None,
        "cancelled_at": run.cancelled_at.isoformat() if run and run.cancelled_at else None,
    }


@router.get("/resilience-scores/{resilience_score_result_id}/summary")
def get_resilience_score_summary(
    resilience_score_result_id: int,
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    result = db.get(ResilienceScoreResult, resilience_score_result_id)
    if not result or result.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    summary = db.execute(
        select(
            func.count(ResilienceScoreItem.id).label("count"),
            func.avg(ResilienceScoreItem.resilience_score).label("avg"),
            func.min(ResilienceScoreItem.resilience_score).label("min"),
            func.max(ResilienceScoreItem.resilience_score).label("max"),
            func.sum(case((ResilienceScoreItem.resilience_score <= 19, 1), else_=0)).label("bucket_0_19"),
            func.sum(case((ResilienceScoreItem.resilience_score.between(20, 39), 1), else_=0)).label("bucket_20_39"),
            func.sum(case((ResilienceScoreItem.resilience_score.between(40, 59), 1), else_=0)).label("bucket_40_59"),
            func.sum(case((ResilienceScoreItem.resilience_score.between(60, 79), 1), else_=0)).label("bucket_60_79"),
            func.sum(case((ResilienceScoreItem.resilience_score >= 80, 1), else_=0)).label("bucket_80_100"),
        )
        .where(
            ResilienceScoreItem.tenant_id == user.tenant_id,
            ResilienceScoreItem.resilience_score_result_id == result.id,
        )
    ).one()

    run = db.get(Run, result.run_id) if result.run_id else None
    output_refs = run.output_refs_json if run and run.output_refs_json else {}

    return {
        "resilience_score_result_id": result.id,
        "count": int(summary.count or 0),
        "avg": float(summary.avg) if summary.avg is not None else None,
        "min": int(summary.min) if summary.min is not None else None,
        "max": int(summary.max) if summary.max is not None else None,
        "scoring_version": result.scoring_version,
        "code_version": result.code_version,
        "hazard_versions_used": result.hazard_versions_json,
        "policy_used": result.policy_used_json or {"policy_pack_version_id": None, "version_label": "default"},
        "policy_pack_version_id": result.policy_pack_version_id,
        "buckets": {
            "0_19": int(summary.bucket_0_19 or 0),
            "20_39": int(summary.bucket_20_39 or 0),
            "40_59": int(summary.bucket_40_59 or 0),
            "60_79": int(summary.bucket_60_79 or 0),
            "80_100": int(summary.bucket_80_100 or 0),
        },
        "scored": output_refs.get("scored"),
        "skipped_missing_coords": output_refs.get("skipped_missing_coords"),
        "with_structural_count": output_refs.get("with_structural_count"),
        "without_structural_count": output_refs.get("without_structural_count"),
        "with_structural": output_refs.get("with_structural_count"),
        "without_structural": output_refs.get("without_structural_count"),
        "peril_coverage": output_refs.get("peril_coverage"),
        "unknown_hazard_fallback_used_count": output_refs.get("unknown_hazard_fallback_used_count"),
        "missing_tiv_count": output_refs.get("missing_tiv_count"),
    }


@router.get("/resilience-scores/{resilience_score_result_id}/items")
def list_resilience_score_items(
    resilience_score_result_id: int,
    limit: int = 100,
    offset: int = 0,
    after_id: Optional[int] = None,
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    result = db.get(ResilienceScoreResult, resilience_score_result_id)
    if not result or result.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    pagination = resolve_keyset_pagination(limit, offset, after_id, max_limit=500)
    limit = pagination["limit"]
    offset = pagination["offset"]
    after_id = pagination["after_id"]

    query = (
        select(ResilienceScoreItem, Location.external_location_id)
        .join(Location, ResilienceScoreItem.location_id == Location.id)
        .where(
            ResilienceScoreItem.tenant_id == user.tenant_id,
            ResilienceScoreItem.resilience_score_result_id == result.id,
        )
        .order_by(ResilienceScoreItem.id.asc())
        .limit(limit)
    )
    if after_id is not None:
        query = query.where(ResilienceScoreItem.id > after_id)
    elif offset is not None:
        query = query.offset(offset)

    rows = db.execute(query).all()

    items = []
    next_after_id = None
    for item, external_location_id in rows:
        warnings = []
        if isinstance(item.result_json, dict):
            warnings = item.result_json.get("warnings") or []
        items.append(
            {
                "location_id": item.location_id,
                "external_location_id": external_location_id,
                "resilience_score": item.resilience_score,
                "risk_score": item.risk_score,
                "warnings": warnings,
            }
        )
        next_after_id = item.id

    return {
        "items": items,
        "limit": limit,
        "offset": offset,
        "after_id": after_id,
        "next_after_id": next_after_id,
    }


@router.get("/resilience-scores/{resilience_score_result_id}/export.csv")
def export_resilience_scores(
    resilience_score_result_id: int,
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
):
    result = db.get(ResilienceScoreResult, resilience_score_result_id)
    if not result or result.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    emit_audit(
        db,
        user.tenant_id,
        user.user_id,
        "resilience_scores_exported",
        {"resilience_score_result_id": resilience_score_result_id},
    )
    generator = iter_resilience_export_rows(db, user.tenant_id, resilience_score_result_id)
    return StreamingResponse(generator, media_type="text/csv")


@router.get("/resilience-scores/{resilience_score_result_id}/disclosure")
def disclosure_resilience_scores(
    resilience_score_result_id: int,
    group_by: Optional[str] = None,
    user: TokenData = Depends(require_role(
        UserRole.ADMIN.value,
        UserRole.OPS.value,
        UserRole.ANALYST.value,
        UserRole.AUDITOR.value,
        UserRole.READ_ONLY.value,
    )),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    result = db.get(ResilienceScoreResult, resilience_score_result_id)
    if not result or result.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    allowed_groups = {"state_region", "postal_code", "lob"}
    if group_by and group_by not in allowed_groups:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group_by")

    run = db.get(Run, result.run_id) if result.run_id else None
    output_refs = run.output_refs_json if run and run.output_refs_json else {}

    bucket_cases = [
        ("0_19", ResilienceScoreItem.resilience_score <= 19),
        ("20_39", ResilienceScoreItem.resilience_score.between(20, 39)),
        ("40_59", ResilienceScoreItem.resilience_score.between(40, 59)),
        ("60_79", ResilienceScoreItem.resilience_score.between(60, 79)),
        ("80_100", ResilienceScoreItem.resilience_score >= 80),
    ]

    tiv_value = func.coalesce(Location.tiv, 0.0)
    score_tiv = func.sum(ResilienceScoreItem.resilience_score * tiv_value).label("score_tiv")
    total_tiv = func.sum(tiv_value).label("total_tiv")
    missing_tiv = func.sum(case((Location.tiv.is_(None), 1), else_=0)).label("missing_tiv_count")

    count_expr = func.count(ResilienceScoreItem.id).label("total_locations")
    bucket_count_exprs = [
        func.sum(case((cond, 1), else_=0)).label(f"count_{name}") for name, cond in bucket_cases
    ]
    bucket_tiv_exprs = [
        func.sum(case((cond, tiv_value), else_=0)).label(f"tiv_{name}") for name, cond in bucket_cases
    ]

    base_query = (
        select(count_expr, total_tiv, score_tiv, missing_tiv, *bucket_count_exprs, *bucket_tiv_exprs)
        .select_from(ResilienceScoreItem)
        .join(Location, ResilienceScoreItem.location_id == Location.id)
        .where(
            ResilienceScoreItem.tenant_id == user.tenant_id,
            ResilienceScoreItem.resilience_score_result_id == result.id,
        )
    )

    if not group_by:
        row = db.execute(base_query).one()
        total_tiv_value = float(row.total_tiv or 0)
        weighted_avg = None
        if total_tiv_value > 0:
            weighted_avg = float(row.score_tiv or 0) / total_tiv_value
        bucket_counts = {name: int(getattr(row, f"count_{name}") or 0) for name, _ in bucket_cases}
        bucket_tiv = {name: float(getattr(row, f"tiv_{name}") or 0) for name, _ in bucket_cases}
        percent_locations = compute_bucket_percentages(bucket_counts, int(row.total_locations or 0))
        percent_tiv = None
        if total_tiv_value > 0:
            percent_tiv = compute_bucket_percentages(bucket_tiv, total_tiv_value)
        return {
            "resilience_score_result_id": result.id,
            "total_locations": int(row.total_locations or 0),
            "total_tiv": total_tiv_value,
            "bucket_counts": bucket_counts,
            "bucket_tiv": bucket_tiv,
            "weighted_avg_score": weighted_avg,
            "missing_tiv_count": int(row.missing_tiv_count or 0),
            "scoring_version": result.scoring_version,
            "code_version": result.code_version,
            "hazard_versions_used": result.hazard_versions_json,
            "policy_used": result.policy_used_json or {"policy_pack_version_id": None, "version_label": "default"},
            "policy_pack_version_id": result.policy_pack_version_id,
            "peril_coverage": output_refs.get("peril_coverage"),
            "disclosure_percentages": {
                "bucket_percent_locations": percent_locations,
                "bucket_percent_tiv": percent_tiv,
            },
        }

    group_col = getattr(Location, group_by)
    grouped_query = base_query.add_columns(group_col.label("group_key")).group_by(group_col)
    grouped_query = grouped_query.order_by(total_tiv.desc()).limit(50)
    rows = db.execute(grouped_query).all()
    groups = []
    for row in rows:
        total_tiv_value = float(row.total_tiv or 0)
        weighted_avg = None
        if total_tiv_value > 0:
            weighted_avg = float(row.score_tiv or 0) / total_tiv_value
        bucket_counts = {name: int(getattr(row, f"count_{name}") or 0) for name, _ in bucket_cases}
        bucket_tiv = {name: float(getattr(row, f"tiv_{name}") or 0) for name, _ in bucket_cases}
        percent_locations = compute_bucket_percentages(bucket_counts, int(row.total_locations or 0))
        percent_tiv = None
        if total_tiv_value > 0:
            percent_tiv = compute_bucket_percentages(bucket_tiv, total_tiv_value)
        groups.append(
            {
                "group_key": row.group_key,
                "total_locations": int(row.total_locations or 0),
                "total_tiv": total_tiv_value,
                "bucket_counts": bucket_counts,
                "bucket_tiv": bucket_tiv,
                "weighted_avg_score": weighted_avg,
                "disclosure_percentages": {
                    "bucket_percent_locations": percent_locations,
                    "bucket_percent_tiv": percent_tiv,
                },
            }
        )
    return {
        "resilience_score_result_id": result.id,
        "group_by": group_by,
        "scoring_version": result.scoring_version,
        "code_version": result.code_version,
        "hazard_versions_used": result.hazard_versions_json,
        "policy_used": result.policy_used_json or {"policy_pack_version_id": None, "version_label": "default"},
        "policy_pack_version_id": result.policy_pack_version_id,
        "peril_coverage": output_refs.get("peril_coverage"),
        "top_groups": groups,
    }


@router.post("/hazard-overlays")
def trigger_hazard_overlays(
    payload: HazardOverlayRequest,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if not payload.hazard_dataset_version_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="hazard_dataset_version_ids required")
    ev = db.get(ExposureVersion, payload.exposure_version_id)
    if not ev or ev.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exposure version not found")
    hazard_dataset_version_id = payload.hazard_dataset_version_ids[0]
    hdv = db.get(HazardDatasetVersion, hazard_dataset_version_id)
    if not hdv or hdv.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hazard dataset version not found")
    run = Run(
        tenant_id=user.tenant_id,
        run_type=RunType.OVERLAY,
        status=RunStatus.QUEUED,
        input_refs_json={"exposure_version_id": payload.exposure_version_id, "hazard_dataset_version_id": hazard_dataset_version_id},
        config_refs_json={"params": payload.params or {}},
        created_by=user.user_id,
        code_version=settings.code_version,
    )
    apply_request_id(run)
    db.add(run)
    db.commit()
    overlay = HazardOverlayResult(
        tenant_id=user.tenant_id,
        exposure_version_id=payload.exposure_version_id,
        hazard_dataset_version_id=hazard_dataset_version_id,
        method="POSTGIS_SPATIAL_JOIN",
        params_json=payload.params or {},
        run_id=run.id,
    )
    db.add(overlay)
    db.commit()
    async_result = overlay_task.delay(
        run.id,
        overlay.id,
        payload.exposure_version_id,
        hazard_dataset_version_id,
        user.tenant_id,
        payload.params,
        run.request_id,
    )
    run.celery_task_id = async_result.id
    db.commit()
    emit_audit(db, user.tenant_id, user.user_id, "overlay_requested", {"overlay_result_id": overlay.id})
    return {"overlay_result_id": overlay.id, "run_id": run.id}


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
    status_value = run.status.value if run and hasattr(run.status, "value") else (run.status if run else "PENDING")
    return {"overlay_result_id": overlay.id, "status": status_value, "run_id": overlay.run_id}


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
    run = db.get(Run, overlay.run_id) if overlay.run_id else None
    summary = None
    if run and run.output_refs_json:
        summary = run.output_refs_json.get("summary")
    return {
        "overlay_result_id": overlay.id,
        "summary": summary,
    }


@router.post("/drift")
def trigger_drift(
    payload: DriftRequest,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ev_a = db.get(ExposureVersion, payload.exposure_version_a)
    ev_b = db.get(ExposureVersion, payload.exposure_version_b)
    if not ev_a or not ev_b or ev_a.tenant_id != user.tenant_id or ev_b.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exposure version not found")
    run = Run(
        tenant_id=user.tenant_id,
        run_type=RunType.DRIFT,
        status=RunStatus.QUEUED,
        input_refs_json={
            "exposure_version_a": payload.exposure_version_a,
            "exposure_version_b": payload.exposure_version_b,
        },
        config_refs_json={"config": payload.config or {}},
        created_by=user.user_id,
        code_version=settings.code_version,
    )
    apply_request_id(run)
    db.add(run)
    db.commit()
    drift_run = DriftRun(
        tenant_id=user.tenant_id,
        exposure_version_a_id=payload.exposure_version_a,
        exposure_version_b_id=payload.exposure_version_b,
        config_json=payload.config or {},
        run_id=run.id,
    )
    db.add(drift_run)
    db.commit()
    async_result = drift_task.delay(
        run.id,
        drift_run.id,
        payload.exposure_version_a,
        payload.exposure_version_b,
        user.tenant_id,
        run.request_id,
    )
    run.celery_task_id = async_result.id
    db.commit()
    emit_audit(db, user.tenant_id, user.user_id, "drift_requested", {"drift_run_id": drift_run.id})
    return {"run_id": run.id, "drift_run_id": drift_run.id, "status": run.status}


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
    drift_run = db.get(DriftRun, drift_run_id)
    if not drift_run or drift_run.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    run = db.get(Run, drift_run.run_id) if drift_run.run_id else None
    summary = None
    if run and run.output_refs_json:
        summary = run.output_refs_json.get("summary")
    if not summary:
        counts = db.execute(
            select(DriftDetail.classification, func.count(DriftDetail.id))
            .where(DriftDetail.drift_run_id == drift_run_id, DriftDetail.tenant_id == user.tenant_id)
            .group_by(DriftDetail.classification)
        ).all()
        summary = {row[0]: row[1] for row in counts}
        summary["total"] = sum(summary.values()) if summary else 0
    return {
        "drift_run_id": drift_run.id,
        "exposure_version_a": drift_run.exposure_version_a_id,
        "exposure_version_b": drift_run.exposure_version_b_id,
        "summary": summary,
        "status": run.status.value if run and hasattr(run.status, "value") else (run.status if run else "PENDING"),
        "created_at": drift_run.created_at.isoformat(),
        "run_id": drift_run.run_id,
        "storage_uri": drift_run.storage_uri,
        "checksum": drift_run.checksum,
    }


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
    drift_run = db.get(DriftRun, drift_run_id)
    if not drift_run or drift_run.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    query = select(DriftDetail).where(
        DriftDetail.drift_run_id == drift_run_id,
        DriftDetail.tenant_id == user.tenant_id,
    )
    if classification:
        query = query.where(DriftDetail.classification == classification)
    total = db.execute(
        select(func.count()).select_from(query.subquery())
    ).scalar_one()
    rows = db.execute(query.order_by(DriftDetail.id.asc()).limit(limit).offset(offset)).scalars().all()
    return {
        "items": [
            {
                "external_location_id": r.external_location_id,
                "classification": r.classification,
                "delta_json": r.delta_json,
            }
            for r in rows
        ],
        "total": total,
    }


@router.post("/rollup-configs")
def create_rollup_config(
    payload: RollupConfigCreate,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    current_version = db.execute(
        select(func.max(RollupConfig.version)).where(
            RollupConfig.tenant_id == user.tenant_id,
            RollupConfig.name == payload.name,
        )
    ).scalar()
    cfg = RollupConfig(
        tenant_id=user.tenant_id,
        name=payload.name,
        version=(current_version or 0) + 1,
        dimensions_json=payload.dimensions_json,
        filters_json=payload.filters_json,
        measures_json=payload.measures_json,
        created_by=user.user_id,
    )
    db.add(cfg)
    db.commit()
    emit_audit(db, user.tenant_id, user.user_id, "rollup_config_created", {"rollup_config_id": cfg.id})
    return {
        "id": cfg.id,
        "name": cfg.name,
        "version": cfg.version,
        "dimensions_json": cfg.dimensions_json,
        "filters_json": cfg.filters_json,
        "measures_json": cfg.measures_json,
        "created_at": cfg.created_at.isoformat(),
    }


@router.get("/rollup-configs")
def list_rollup_configs(user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    rows = db.execute(
        select(RollupConfig)
        .where(RollupConfig.tenant_id == user.tenant_id)
        .order_by(RollupConfig.created_at.desc())
    ).scalars().all()
    return {"items": [
        {
            "id": r.id,
            "name": r.name,
            "version": r.version,
            "dimensions_json": r.dimensions_json,
            "filters_json": r.filters_json,
            "measures_json": r.measures_json,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]}


@router.post("/rollups")
def trigger_rollup(
    payload: RollupRequest,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ev = db.get(ExposureVersion, payload.exposure_version_id)
    if not ev or ev.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exposure version not found")
    cfg = db.get(RollupConfig, payload.rollup_config_id)
    if not cfg or cfg.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rollup config not found")
    run = Run(
        tenant_id=user.tenant_id,
        run_type=RunType.ROLLUP,
        status=RunStatus.QUEUED,
        input_refs_json={
            "exposure_version_id": payload.exposure_version_id,
            "hazard_overlay_result_ids": payload.hazard_overlay_result_ids,
        },
        config_refs_json={"rollup_config_id": payload.rollup_config_id},
        created_by=user.user_id,
        code_version=settings.code_version,
    )
    apply_request_id(run)
    db.add(run)
    db.commit()
    rollup_result = RollupResult(
        tenant_id=user.tenant_id,
        exposure_version_id=payload.exposure_version_id,
        rollup_config_id=payload.rollup_config_id,
        hazard_overlay_result_ids_json=payload.hazard_overlay_result_ids,
        run_id=run.id,
    )
    db.add(rollup_result)
    db.commit()
    async_result = rollup_task.delay(
        run.id,
        rollup_result.id,
        payload.exposure_version_id,
        payload.rollup_config_id,
        payload.hazard_overlay_result_ids,
        user.tenant_id,
        run.request_id,
    )
    run.celery_task_id = async_result.id
    db.commit()
    emit_audit(db, user.tenant_id, user.user_id, "rollup_requested", {"rollup_result_id": rollup_result.id})
    return {"id": rollup_result.id, "run_id": run.id}


@router.get("/rollups/{rollup_result_id}")
def rollup_result_detail(rollup_result_id: int, user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    rr = db.get(RollupResult, rollup_result_id)
    if not rr or rr.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    items = db.execute(
        select(RollupResultItem)
        .where(
            RollupResultItem.tenant_id == user.tenant_id,
            RollupResultItem.rollup_result_id == rollup_result_id,
        )
        .order_by(RollupResultItem.id.asc())
    ).scalars().all()
    return {"items": [
        {
            "rollup_key": json.dumps(item.rollup_key_json, sort_keys=True),
            "rollup_key_json": item.rollup_key_json,
            "metrics": item.metrics_json,
        }
        for item in items
    ]}


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
    rr = db.get(RollupResult, rollup_result_id)
    if not rr or rr.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        padded = rollup_key_b64 + "=" * (-len(rollup_key_b64) % 4)
        key_json = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid rollup key") from exc
    query = select(Location).where(
        Location.tenant_id == user.tenant_id,
        Location.exposure_version_id == rr.exposure_version_id,
    )
    for field, value in (key_json or {}).items():
        if hasattr(Location, field):
            query = query.where(getattr(Location, field) == value)
    rows = db.execute(query).scalars().all()
    return {"items": [
        {
            "external_location_id": r.external_location_id,
            "address_line1": r.address_line1,
            "city": r.city,
            "state_region": r.state_region,
            "postal_code": r.postal_code,
            "country": r.country,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "tiv": r.tiv,
            "lob": r.lob,
            "product_code": r.product_code,
            "quality_tier": r.quality_tier,
        }
        for r in rows
    ]}

@router.post("/threshold-rules")
def create_threshold_rule(
    payload: ThresholdRuleCreate,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    rule = ThresholdRule(
        tenant_id=user.tenant_id,
        name=payload.name,
        rule_json=payload.rule_json,
        severity=payload.severity,
        active=payload.active,
        created_by=user.user_id,
    )
    db.add(rule)
    db.commit()
    emit_audit(db, user.tenant_id, user.user_id, "threshold_rule_created", {"threshold_rule_id": rule.id})
    return {
        "id": rule.id,
        "name": rule.name,
        "severity": rule.severity,
        "active": rule.active,
        "rule_json": rule.rule_json,
        "created_at": rule.created_at.isoformat(),
    }


@router.get("/threshold-rules")
def list_threshold_rules(user: TokenData = Depends(require_role(
    UserRole.ADMIN.value,
    UserRole.OPS.value,
    UserRole.ANALYST.value,
    UserRole.AUDITOR.value,
    UserRole.READ_ONLY.value,
)), db: Session = Depends(get_db)) -> Dict[str, Any]:
    rows = db.execute(
        select(ThresholdRule)
        .where(ThresholdRule.tenant_id == user.tenant_id)
        .order_by(ThresholdRule.created_at.desc())
    ).scalars().all()
    return {"items": [
        {
            "id": r.id,
            "name": r.name,
            "severity": r.severity,
            "active": r.active,
            "rule_json": r.rule_json,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]}


@router.post("/breaches/run")
def run_breach_eval(
    payload: BreachEvalRequest,
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    rr = db.get(RollupResult, payload.rollup_result_id)
    if not rr or rr.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rollup result not found")
    run = Run(
        tenant_id=user.tenant_id,
        run_type=RunType.BREACH_EVAL,
        status=RunStatus.QUEUED,
        input_refs_json={"rollup_result_id": payload.rollup_result_id},
        config_refs_json={"threshold_rule_ids": payload.threshold_rule_ids or []},
        created_by=user.user_id,
        code_version=settings.code_version,
    )
    apply_request_id(run)
    db.add(run)
    db.commit()
    async_result = breach_task.delay(
        run.id,
        payload.rollup_result_id,
        payload.threshold_rule_ids,
        user.tenant_id,
        run.request_id,
    )
    run.celery_task_id = async_result.id
    db.commit()
    emit_audit(db, user.tenant_id, user.user_id, "breach_eval_requested", {"rollup_result_id": payload.rollup_result_id})
    return {"run_id": run.id, "status": run.status}


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
    query = (
        select(Breach, ThresholdRule.name.label("rule_name"))
        .join(ThresholdRule, ThresholdRule.id == Breach.threshold_rule_id)
        .where(Breach.tenant_id == user.tenant_id)
    )
    if status_filter:
        query = query.where(Breach.status == status_filter)
    if exposure_version_id:
        query = query.where(Breach.exposure_version_id == exposure_version_id)
    if threshold_rule_id:
        query = query.where(Breach.threshold_rule_id == threshold_rule_id)
    rows = db.execute(query.order_by(Breach.last_seen_at.desc())).all()
    return {"items": [
        {
            "id": breach.id,
            "status": breach.status,
            "rule_id": breach.threshold_rule_id,
            "rule_name": rule_name,
            "exposure_version_id": breach.exposure_version_id,
            "rollup_result_id": breach.rollup_result_id,
            "rollup_key": json.dumps(breach.rollup_key_json, sort_keys=True),
            "metric_name": breach.metric_name,
            "metric_value": breach.metric_value,
            "threshold_value": breach.threshold_value,
            "first_seen_at": breach.first_seen_at.isoformat(),
            "last_seen_at": breach.last_seen_at.isoformat(),
        }
        for breach, rule_name in rows
    ]}


@router.patch("/breaches/{breach_id}")
def update_breach_status(
    breach_id: int,
    payload: Dict[str, str],
    user: TokenData = Depends(require_role(UserRole.ADMIN.value, UserRole.OPS.value, UserRole.ANALYST.value)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    breach = db.get(Breach, breach_id)
    if not breach or breach.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    status_value = payload.get("status")
    if status_value not in {"OPEN", "ACKED", "RESOLVED"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
    breach.status = status_value
    breach.last_seen_at = datetime.utcnow()
    if status_value == "RESOLVED":
        breach.resolved_at = datetime.utcnow()
    db.commit()
    emit_audit(db, user.tenant_id, user.user_id, "breach_status_updated", {"breach_id": breach.id, "status": status_value})
    return {
        "id": breach.id,
        "status": breach.status,
        "resolved_at": breach.resolved_at.isoformat() if breach.resolved_at else None,
    }


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
    lineage = build_lineage(db, user.tenant_id, entity_type, entity_id)
    if not lineage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return lineage


@router.get("/runs")
def list_runs(
    status_filter: Optional[str] = None,
    run_type: Optional[str] = None,
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
    query = select(Run).where(Run.tenant_id == user.tenant_id)
    if status_filter:
        try:
            status_enum = RunStatus(status_filter)
            query = query.where(Run.status == status_enum)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status") from exc
    if run_type:
        try:
            run_type_enum = RunType(run_type)
            query = query.where(Run.run_type == run_type_enum)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid run_type") from exc
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = db.execute(
        query.order_by(Run.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()
    return {"items": [serialize_run(r) for r in rows], "total": total}


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
    return serialize_run(run)


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
