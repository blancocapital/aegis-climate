"""
Add request fingerprint to resilience score results

Revision ID: 0021_resilience_score_request_fingerprint
Revises: 0020_property_profile_table
Create Date: 2024-01-01 00:00:21
"""
import hashlib
import json

from alembic import op
import sqlalchemy as sa

revision = "0021_resilience_score_request_fingerprint"
down_revision = "0020_property_profile_table"
branch_labels = None
depends_on = None


def _canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _fingerprint(payload):
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def upgrade():
    op.add_column("resilience_score_result", sa.Column("request_fingerprint", sa.String(), nullable=True))
    op.add_column("resilience_score_result", sa.Column("request_json", sa.JSON(), nullable=True))

    bind = op.get_bind()
    table = sa.table(
        "resilience_score_result",
        sa.column("id", sa.Integer),
        sa.column("request_fingerprint", sa.String),
        sa.column("request_json", sa.JSON),
        sa.column("tenant_id", sa.String),
        sa.column("exposure_version_id", sa.Integer),
        sa.column("hazard_dataset_version_ids_json", sa.JSON),
        sa.column("scoring_config_json", sa.JSON),
        sa.column("scoring_version", sa.String),
        sa.column("code_version", sa.String),
    )
    rows = bind.execute(
        sa.select(
            table.c.id,
            table.c.tenant_id,
            table.c.exposure_version_id,
            table.c.hazard_dataset_version_ids_json,
            table.c.scoring_config_json,
            table.c.scoring_version,
            table.c.code_version,
        )
    ).all()
    for row in rows:
        hazard_ids = row.hazard_dataset_version_ids_json or []
        if not isinstance(hazard_ids, list):
            hazard_ids = []
        payload = {
            "tenant_id": row.tenant_id,
            "exposure_version_id": row.exposure_version_id,
            "hazard_dataset_version_ids": sorted(hazard_ids),
            "config": row.scoring_config_json or {},
            "scoring_version": row.scoring_version,
            "code_version": row.code_version,
        }
        fingerprint = _fingerprint(payload)
        bind.execute(
            table.update()
            .where(table.c.id == row.id)
            .values(request_fingerprint=fingerprint, request_json=payload)
        )

    op.alter_column("resilience_score_result", "request_fingerprint", nullable=False)
    op.create_unique_constraint(
        "uq_resilience_score_request",
        "resilience_score_result",
        ["tenant_id", "request_fingerprint"],
    )


def downgrade():
    op.drop_constraint("uq_resilience_score_request", "resilience_score_result", type_="unique")
    op.drop_column("resilience_score_result", "request_json")
    op.drop_column("resilience_score_result", "request_fingerprint")
