"""
Add tenant default policy pack version

Revision ID: 0027_tenant_default_policy
Revises: 0026_res_policy_link
Create Date: 2024-01-01 00:00:27
"""
from alembic import op
import sqlalchemy as sa

revision = "0027_tenant_default_policy"
down_revision = "0026_res_policy_link"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tenant",
        sa.Column(
            "default_policy_pack_version_id",
            sa.Integer(),
            sa.ForeignKey("policy_pack_version.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_tenant_default_policy_pack",
        "tenant",
        ["default_policy_pack_version_id"],
    )


def downgrade():
    op.drop_index("ix_tenant_default_policy_pack", table_name="tenant")
    op.drop_column("tenant", "default_policy_pack_version_id")
