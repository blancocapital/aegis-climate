"""
Add resilience score result tables

Revision ID: 0015_resilience_score_tables
Revises: 0014_run_resilience_enum
Create Date: 2024-01-01 00:00:15
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_resilience_score_tables"
down_revision = "0014_run_resilience_enum"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "resilience_score_result",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "exposure_version_id",
            sa.Integer(),
            sa.ForeignKey("exposure_version.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("run.id", ondelete="SET NULL")),
        sa.Column("hazard_dataset_version_ids_json", sa.JSON(), nullable=True),
        sa.Column("scoring_config_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_resilience_score_result_tenant_created",
        "resilience_score_result",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "resilience_score_item",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "resilience_score_result_id",
            sa.Integer(),
            sa.ForeignKey("resilience_score_result.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("location.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("resilience_score", sa.Integer(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("hazards_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id",
            "resilience_score_result_id",
            "location_id",
            name="uq_resilience_score_item_unique",
        ),
    )
    op.create_index(
        "ix_resilience_score_item_tenant_result",
        "resilience_score_item",
        ["tenant_id", "resilience_score_result_id"],
    )
    op.create_index(
        "ix_resilience_score_item_result_score",
        "resilience_score_item",
        ["resilience_score_result_id", "resilience_score"],
    )


def downgrade():
    op.drop_index("ix_resilience_score_item_result_score", table_name="resilience_score_item")
    op.drop_index("ix_resilience_score_item_tenant_result", table_name="resilience_score_item")
    op.drop_table("resilience_score_item")
    op.drop_index("ix_resilience_score_result_tenant_created", table_name="resilience_score_result")
    op.drop_table("resilience_score_result")
