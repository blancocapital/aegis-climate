"""
Add UW eval run type

Revision ID: 0028_run_uw_eval_enum
Revises: 0027_tenant_default_policy
Create Date: 2025-01-01 00:00:28
"""
from alembic import op

revision = "0028_run_uw_eval_enum"
down_revision = "0027_tenant_default_policy"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE runtype ADD VALUE IF NOT EXISTS 'UW_EVAL'")


def downgrade():
    pass
