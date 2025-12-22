import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
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


class RunStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class Tenant(Base):
    __tablename__ = "tenant"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True)
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
    metadata = Column(JSON, nullable=True)
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
    summary_json = Column(JSON, nullable=False)
    row_errors_uri = Column(String, nullable=False)
    checksum = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_validation_tenant_created", "tenant_id", "created_at"),)


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
    country = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    tiv = Column(Float, nullable=True)
    limit = Column(Float, nullable=True)
    premium = Column(Float, nullable=True)
    geocode_method = Column(String, nullable=True)
    geocode_confidence = Column(Float, nullable=True)
    quality_tier = Column(String, nullable=True)
    quality_reasons_json = Column(JSON, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "exposure_version_id", "external_location_id", name="uq_location_unique"),
        Index("ix_location_tenant_created", "tenant_id", "created_at"),
    )
