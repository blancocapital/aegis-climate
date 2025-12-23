import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from geoalchemy2 import Geometry
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    OPS = "OPS"
    ANALYST = "ANALYST"
    AUDITOR = "AUDITOR"
    READ_ONLY = "READ_ONLY"


class RunType(str, enum.Enum):
    VALIDATION = "VALIDATION"
    COMMIT = "COMMIT"
    GEOCODE = "GEOCODE"
    OVERLAY = "OVERLAY"
    ROLLUP = "ROLLUP"
    BREACH_EVAL = "BREACH_EVAL"
    DRIFT = "DRIFT"
    RESILIENCE_SCORE = "RESILIENCE_SCORE"


class RunStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class Tenant(Base):
    __tablename__ = "tenant"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    default_currency = Column(String, nullable=False, default="USD")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class User(Base):
    __tablename__ = "user"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    email = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant")

    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),)


class AuditEvent(Base):
    __tablename__ = "audit_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("user.id", ondelete="SET NULL"))
    action = Column(String, nullable=False)
    metadata_json = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_audit_event_tenant_created", "tenant_id", "created_at"),)


class Run(Base):
    __tablename__ = "run"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    run_type = Column(Enum(RunType), nullable=False)
    status = Column(Enum(RunStatus), nullable=False)
    input_refs_json = Column(JSON, nullable=True)
    config_refs_json = Column(JSON, nullable=True)
    output_refs_json = Column(JSON, nullable=True)
    artifact_checksums_json = Column(JSON, nullable=True)
    code_version = Column(String, nullable=True)
    created_by = Column(String, ForeignKey("user.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("ix_run_tenant_created", "tenant_id", "created_at"),)


class ExposureUpload(Base):
    __tablename__ = "exposure_upload"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String, nullable=False)
    object_uri = Column(String, nullable=False)
    checksum = Column(String, nullable=False)
    idempotency_key = Column(String, nullable=True)
    created_by = Column(String, ForeignKey("user.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    mapping_template_id = Column(Integer, ForeignKey("mapping_template.id"))

    __table_args__ = (
        Index("ix_upload_tenant_created", "tenant_id", "created_at"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_upload_tenant_idempotency"),
    )


class MappingTemplate(Base):
    __tablename__ = "mapping_template"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    version = Column(Integer, nullable=False)
    template_json = Column(JSON, nullable=False)
    created_by = Column(String, ForeignKey("user.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "version", name="uq_mapping_template_version"),
        Index("ix_mapping_tenant_created", "tenant_id", "created_at"),
    )


class ValidationResult(Base):
    __tablename__ = "validation_result"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    upload_id = Column(String, ForeignKey("exposure_upload.id", ondelete="CASCADE"), nullable=False)
    mapping_template_id = Column(Integer, ForeignKey("mapping_template.id", ondelete="SET NULL"), nullable=True)
    summary_json = Column(JSON, nullable=False)
    row_errors_uri = Column(String, nullable=False)
    checksum = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_validation_tenant_created", "tenant_id", "created_at"),)


class DriftRun(Base):
    __tablename__ = "drift_run"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    exposure_version_a_id = Column(Integer, ForeignKey("exposure_version.id", ondelete="CASCADE"), nullable=False)
    exposure_version_b_id = Column(Integer, ForeignKey("exposure_version.id", ondelete="CASCADE"), nullable=False)
    config_json = Column(JSON, nullable=True)
    storage_uri = Column(String, nullable=True)
    checksum = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    run_id = Column(Integer, ForeignKey("run.id", ondelete="SET NULL"))

    __table_args__ = (Index("ix_drift_run_tenant_created", "tenant_id", "created_at"),)


class DriftDetail(Base):
    __tablename__ = "drift_detail"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    drift_run_id = Column(Integer, ForeignKey("drift_run.id", ondelete="CASCADE"), nullable=False)
    external_location_id = Column(String, nullable=False)
    classification = Column(String, nullable=False)
    delta_json = Column(JSON, nullable=False)

    __table_args__ = (
        Index("ix_drift_detail_tenant_run", "tenant_id", "drift_run_id"),
        Index("ix_drift_detail_run_class", "drift_run_id", "classification"),
        UniqueConstraint(
            "tenant_id", "drift_run_id", "external_location_id", name="uq_drift_detail_unique"
        ),
    )


class ExposureVersion(Base):
    __tablename__ = "exposure_version"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    upload_id = Column(String, ForeignKey("exposure_upload.id", ondelete="SET NULL"))
    mapping_template_id = Column(Integer, ForeignKey("mapping_template.id", ondelete="SET NULL"))
    name = Column(String, nullable=False)
    idempotency_key = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_exposure_version_tenant_created", "tenant_id", "created_at"),)


class Location(Base):
    __tablename__ = "location"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    exposure_version_id = Column(Integer, ForeignKey("exposure_version.id", ondelete="CASCADE"), nullable=False)
    external_location_id = Column(String, nullable=False)
    address_line1 = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state_region = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    country = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    lob = Column(String, nullable=True)
    product_code = Column(String, nullable=True)
    tiv = Column(Float, nullable=True)
    limit = Column(Float, nullable=True)
    premium = Column(Float, nullable=True)
    geocode_method = Column(String, nullable=True)
    geocode_confidence = Column(Float, nullable=True)
    quality_tier = Column(String, nullable=True)
    quality_reasons_json = Column(JSON, nullable=True)
    structural_json = Column(JSON, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "exposure_version_id", "external_location_id", name="uq_location_unique"),
        Index("ix_location_tenant_created", "tenant_id", "created_at"),
    )


class HazardDataset(Base):
    __tablename__ = "hazard_dataset"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    peril = Column(String, nullable=False)
    vendor = Column(String, nullable=True)
    coverage_geo = Column(String, nullable=True)
    license_ref = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_hazard_dataset_tenant_created", "tenant_id", "created_at"),)


class HazardDatasetVersion(Base):
    __tablename__ = "hazard_dataset_version"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    hazard_dataset_id = Column(Integer, ForeignKey("hazard_dataset.id", ondelete="CASCADE"), nullable=False)
    version_label = Column(String, nullable=False)
    storage_uri = Column(String, nullable=False)
    checksum = Column(String, nullable=False)
    effective_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_hazard_dataset_version_tenant_created", "tenant_id", "created_at"),
        UniqueConstraint("tenant_id", "hazard_dataset_id", "version_label", name="uq_hazard_dataset_version"),
    )


class HazardFeaturePolygon(Base):
    __tablename__ = "hazard_feature_polygon"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    hazard_dataset_version_id = Column(Integer, ForeignKey("hazard_dataset_version.id", ondelete="CASCADE"), nullable=False)
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    properties_json = Column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_hazard_feature_polygon_tenant", "tenant_id"),
    )


class HazardOverlayResult(Base):
    __tablename__ = "hazard_overlay_result"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    exposure_version_id = Column(Integer, ForeignKey("exposure_version.id", ondelete="CASCADE"), nullable=False)
    hazard_dataset_version_id = Column(Integer, ForeignKey("hazard_dataset_version.id", ondelete="CASCADE"), nullable=False)
    method = Column(String, nullable=False)
    params_json = Column(JSON, nullable=True)
    run_id = Column(Integer, ForeignKey("run.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_hazard_overlay_tenant_created", "tenant_id", "created_at"),)


class ResilienceScoreResult(Base):
    __tablename__ = "resilience_score_result"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    exposure_version_id = Column(Integer, ForeignKey("exposure_version.id", ondelete="CASCADE"), nullable=False)
    run_id = Column(Integer, ForeignKey("run.id", ondelete="SET NULL"))
    hazard_dataset_version_ids_json = Column(JSON, nullable=True)
    scoring_config_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_resilience_score_result_tenant_created", "tenant_id", "created_at"),)


class ResilienceScoreItem(Base):
    __tablename__ = "resilience_score_item"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    resilience_score_result_id = Column(
        Integer, ForeignKey("resilience_score_result.id", ondelete="CASCADE"), nullable=False
    )
    location_id = Column(Integer, ForeignKey("location.id", ondelete="CASCADE"), nullable=False)
    resilience_score = Column(Integer, nullable=False)
    risk_score = Column(Float, nullable=False)
    hazards_json = Column(JSON, nullable=False)
    result_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "resilience_score_result_id",
            "location_id",
            name="uq_resilience_score_item_unique",
        ),
        Index("ix_resilience_score_item_tenant_result", "tenant_id", "resilience_score_result_id"),
        Index("ix_resilience_score_item_result_score", "resilience_score_result_id", "resilience_score"),
    )


class LocationHazardAttribute(Base):
    __tablename__ = "location_hazard_attribute"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    location_id = Column(Integer, ForeignKey("location.id", ondelete="CASCADE"), nullable=False)
    hazard_overlay_result_id = Column(Integer, ForeignKey("hazard_overlay_result.id", ondelete="CASCADE"), nullable=False)
    attributes_json = Column(JSON, nullable=False)

    __table_args__ = (Index("ix_location_hazard_attr_tenant", "tenant_id"),)


class RollupConfig(Base):
    __tablename__ = "rollup_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    version = Column(Integer, nullable=False)
    dimensions_json = Column(JSON, nullable=False)
    filters_json = Column(JSON, nullable=True)
    measures_json = Column(JSON, nullable=False)
    created_by = Column(String, ForeignKey("user.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "version", name="uq_rollup_config_version"),
        Index("ix_rollup_config_tenant_created", "tenant_id", "created_at"),
    )


class RollupResult(Base):
    __tablename__ = "rollup_result"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    exposure_version_id = Column(Integer, ForeignKey("exposure_version.id", ondelete="CASCADE"), nullable=False)
    rollup_config_id = Column(Integer, ForeignKey("rollup_config.id", ondelete="CASCADE"), nullable=False)
    hazard_overlay_result_ids_json = Column(JSON, nullable=True)
    storage_uri = Column(String, nullable=True)
    checksum = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    run_id = Column(Integer, ForeignKey("run.id", ondelete="SET NULL"))

    __table_args__ = (
        Index("ix_rollup_result_tenant_created", "tenant_id", "created_at"),
    )


class RollupResultItem(Base):
    __tablename__ = "rollup_result_item"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    rollup_result_id = Column(Integer, ForeignKey("rollup_result.id", ondelete="CASCADE"), nullable=False)
    rollup_key_json = Column(JSON, nullable=False)
    rollup_key_hash = Column(String, nullable=False)
    metrics_json = Column(JSON, nullable=False)

    __table_args__ = (
        Index("ix_rollup_item_tenant_result", "tenant_id", "rollup_result_id"),
        UniqueConstraint("tenant_id", "rollup_result_id", "rollup_key_hash", name="uq_rollup_item_unique"),
    )


class ThresholdRule(Base):
    __tablename__ = "threshold_rule"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    rule_json = Column(JSON, nullable=False)
    severity = Column(String, nullable=False)
    active = Column(Boolean, nullable=False)
    created_by = Column(String, ForeignKey("user.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_threshold_rule_tenant_created", "tenant_id", "created_at"),)


class Breach(Base):
    __tablename__ = "breach"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    exposure_version_id = Column(Integer, ForeignKey("exposure_version.id", ondelete="CASCADE"), nullable=False)
    rollup_result_id = Column(Integer, ForeignKey("rollup_result.id", ondelete="CASCADE"), nullable=False)
    threshold_rule_id = Column(Integer, ForeignKey("threshold_rule.id", ondelete="CASCADE"), nullable=False)
    rollup_key_json = Column(JSON, nullable=False)
    rollup_key_hash = Column(String, nullable=False)
    metric_name = Column(String, nullable=False)
    metric_value = Column(Float, nullable=False)
    threshold_value = Column(Float, nullable=False)
    status = Column(String, nullable=False)
    first_seen_at = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    last_eval_run_id = Column(Integer, ForeignKey("run.id", ondelete="SET NULL"))

    __table_args__ = (
        Index("ix_breach_tenant_status_last_seen", "tenant_id", "status", "last_seen_at"),
        UniqueConstraint(
            "tenant_id", "threshold_rule_id", "exposure_version_id", "rollup_key_hash", name="uq_breach_unique"
        ),
    )
