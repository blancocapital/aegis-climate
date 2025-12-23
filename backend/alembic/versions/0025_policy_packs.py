"""
Add policy pack tables

Revision ID: 0025_policy_packs
Revises: 0024_run_cancelled_enum
Create Date: 2024-01-01 00:00:25
"""
from alembic import op
import sqlalchemy as sa

revision = "0025_policy_packs"
down_revision = "0024_run_cancelled_enum"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "policy_pack",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_policy_pack_tenant_created", "policy_pack", ["tenant_id", "created_at"])

    op.create_table(
        "policy_pack_version",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_pack_id", sa.Integer(), sa.ForeignKey("policy_pack.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_label", sa.String(), nullable=False),
        sa.Column("scoring_config_json", sa.JSON(), nullable=True),
        sa.Column("underwriting_policy_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "policy_pack_id", "version_label", name="uq_policy_pack_version"),
    )
    op.create_index(
        "ix_policy_pack_version_tenant_pack_created",
        "policy_pack_version",
        ["tenant_id", "policy_pack_id", "created_at"],
    )


def downgrade():
    op.drop_index("ix_policy_pack_version_tenant_pack_created", table_name="policy_pack_version")
    op.drop_table("policy_pack_version")
    op.drop_index("ix_policy_pack_tenant_created", table_name="policy_pack")
    op.drop_table("policy_pack")
