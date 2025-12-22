import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..core.auth import TokenData, create_access_token, get_current_user, require_role

router = APIRouter()


@router.post("/auth/login")
def login(tenant_id: str, user_id: str, role: str) -> Dict[str, str]:
    token = create_access_token(tenant_id=tenant_id, role=role, user_id=user_id)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/uploads")
def create_upload(user: TokenData = Depends(require_role("ADMIN", "OPS"))) -> Dict[str, Any]:
    upload_id = str(uuid.uuid4())
    return {"upload_id": upload_id, "upload_url": f"s3://uploads/{upload_id}"}


@router.post("/uploads/{upload_id}/mapping")
def attach_mapping(upload_id: str, mapping_name: str, version: int = 1, user: TokenData = Depends(require_role("ADMIN", "OPS"))) -> Dict[str, Any]:
    return {"upload_id": upload_id, "mapping_template": {"name": mapping_name, "version": version}}


@router.post("/uploads/{upload_id}/validate")
def validate_upload(upload_id: str, user: TokenData = Depends(require_role("ADMIN", "OPS"))) -> Dict[str, Any]:
    job_id = str(uuid.uuid4())
    return {"upload_id": upload_id, "job_id": job_id, "summary": {"errors": 0, "warnings": 0}, "row_errors_uri": f"s3://validations/{upload_id}/errors.json"}


@router.post("/uploads/{upload_id}/commit")
def commit_upload(upload_id: str, name: Optional[str] = None, user: TokenData = Depends(require_role("ADMIN", "OPS"))) -> Dict[str, Any]:
    exposure_version_id = str(uuid.uuid4())
    return {"exposure_version_id": exposure_version_id, "name": name or f"Exposure {upload_id}"}


@router.get("/exposure-versions")
def list_exposure_versions(user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    return {"items": []}


@router.get("/exposure-versions/{exposure_version_id}/summary")
def exposure_summary(exposure_version_id: str, user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    return {"exposure_version_id": exposure_version_id, "locations": 0, "tiv": 0}


@router.get("/exposure-versions/{exposure_version_id}/locations")
def exposure_locations(exposure_version_id: str, page: int = 1, page_size: int = 50, user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    return {"exposure_version_id": exposure_version_id, "page": page, "page_size": page_size, "items": []}


@router.get("/exposure-versions/{exposure_version_id}/exceptions")
def exposure_exceptions(exposure_version_id: str, user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    return {"exposure_version_id": exposure_version_id, "items": []}


@router.post("/hazard-overlays")
def run_overlay(exposure_version_id: str, hazard_dataset_version_ids: List[str], user: TokenData = Depends(require_role("ADMIN", "OPS", "ANALYST"))) -> Dict[str, Any]:
    overlay_id = str(uuid.uuid4())
    return {"hazard_overlay_result_id": overlay_id, "status": "QUEUED"}


@router.get("/hazard-overlays/{overlay_id}/status")
def overlay_status(overlay_id: str, user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    return {"hazard_overlay_result_id": overlay_id, "status": "SUCCEEDED"}


@router.get("/hazard-overlays/{overlay_id}/summary")
def overlay_summary(overlay_id: str, user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    return {"hazard_overlay_result_id": overlay_id, "summary": {}}


@router.post("/rollup-configs")
def create_rollup_config(name: str, user: TokenData = Depends(require_role("ADMIN", "ANALYST"))) -> Dict[str, Any]:
    return {"rollup_config_id": str(uuid.uuid4()), "name": name}


@router.post("/rollups")
def run_rollup(exposure_version_id: str, rollup_config_id: str, hazard_overlay_result_ids: Optional[List[str]] = None, user: TokenData = Depends(require_role("ADMIN", "OPS", "ANALYST"))) -> Dict[str, Any]:
    rollup_id = str(uuid.uuid4())
    return {"rollup_result_id": rollup_id, "status": "QUEUED"}


@router.get("/rollups/{rollup_id}")
def get_rollup(rollup_id: str, user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    return {"rollup_result_id": rollup_id, "data": []}


@router.get("/rollups/{rollup_id}/drilldown")
def rollup_drilldown(rollup_id: str, rollup_key: str = Query(..., description="Composite rollup key"), user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    return {"rollup_result_id": rollup_id, "rollup_key": rollup_key, "contributors": []}


@router.post("/threshold-rules")
def create_threshold(name: str, severity: str, user: TokenData = Depends(require_role("ADMIN", "ANALYST"))) -> Dict[str, Any]:
    return {"threshold_rule_id": str(uuid.uuid4()), "name": name, "severity": severity}


@router.post("/breaches/run")
def run_breaches(exposure_version_id: str, threshold_rule_ids: List[str], rollup_result_id: str, user: TokenData = Depends(require_role("ADMIN", "OPS", "ANALYST"))) -> Dict[str, Any]:
    breach_ids = [str(uuid.uuid4()) for _ in threshold_rule_ids]
    return {"breach_ids": breach_ids, "status": "SUCCEEDED"}


@router.get("/breaches")
def list_breaches(exposure_version_id: Optional[str] = None, user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    return {"items": []}


@router.patch("/breaches/{breach_id}")
def update_breach(breach_id: str, status: str, user: TokenData = Depends(require_role("ADMIN", "OPS"))) -> Dict[str, Any]:
    if status not in {"OPEN", "ACKED", "RESOLVED"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
    return {"breach_id": breach_id, "status": status}


@router.post("/drift")
def run_drift(exposure_version_a: str, exposure_version_b: str, user: TokenData = Depends(require_role("ADMIN", "OPS", "ANALYST"))) -> Dict[str, Any]:
    drift_id = str(uuid.uuid4())
    return {"drift_run_id": drift_id, "status": "QUEUED"}


@router.get("/drift/{drift_run_id}")
def drift_summary(drift_run_id: str, user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    return {"drift_run_id": drift_run_id, "summary": {}}


@router.get("/drift/{drift_run_id}/details")
def drift_details(drift_run_id: str, user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    return {"drift_run_id": drift_run_id, "items": []}


@router.get("/runs/{run_id}")
def get_run(run_id: str, user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    return {"run_id": run_id, "status": "SUCCEEDED"}


@router.get("/lineage")
def get_lineage(entity_type: str, entity_id: str, user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    return {"entity_type": entity_type, "entity_id": entity_id, "lineage": []}


@router.get("/audit-events")
def list_audit_events(user: TokenData = Depends(get_current_user)) -> Dict[str, Any]:
    return {"items": []}


@router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}
