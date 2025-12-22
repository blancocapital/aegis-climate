"""
Create drift_run and drift_detail tables

Revision ID: 0012_drift_tables
Revises: 0011_validation_mapping_template
Create Date: 2024-01-01 00:00:12
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_drift_tables"
down_revision = "0011_validation_mapping_template"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "drift_run",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "exposure_version_a_id",
            sa.Integer(),
            sa.ForeignKey("exposure_version.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "exposure_version_b_id",
            sa.Integer(),
            sa.ForeignKey("exposure_version.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("storage_uri", sa.String(), nullable=True),
        sa.Column("checksum", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("run.id", ondelete="SET NULL")),
    )
    op.create_index("ix_drift_run_tenant_created", "drift_run", ["tenant_id", "created_at"])

    op.create_table(
        "drift_detail",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("drift_run_id", sa.Integer(), sa.ForeignKey("drift_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_location_id", sa.String(), nullable=False),
        sa.Column("classification", sa.String(), nullable=False),
        sa.Column("delta_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_drift_detail_tenant_run", "drift_detail", ["tenant_id", "drift_run_id"])
    op.create_index("ix_drift_detail_run_class", "drift_detail", ["drift_run_id", "classification"])
    op.create_unique_constraint(
        "uq_drift_detail_unique",
        "drift_detail",
        ["tenant_id", "drift_run_id", "external_location_id"],
    )


def downgrade():
    op.drop_constraint("uq_drift_detail_unique", "drift_detail", type_="unique")
    op.drop_index("ix_drift_detail_run_class", table_name="drift_detail")
    op.drop_index("ix_drift_detail_tenant_run", table_name="drift_detail")
    op.drop_table("drift_detail")
    op.drop_index("ix_drift_run_tenant_created", table_name="drift_run")
    op.drop_table("drift_run")
