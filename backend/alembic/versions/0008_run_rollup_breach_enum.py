"""add rollup and breach run types

Revision ID: 0008_run_rollup_breach_enum
Revises: 0007_hazard_registry_overlay
Create Date: 2024-01-01 00:00:08
"""
from alembic import op

revision = '0008_run_rollup_breach_enum'
down_revision = '0007_hazard_registry_overlay'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE runtype ADD VALUE IF NOT EXISTS 'ROLLUP'")
    op.execute("ALTER TYPE runtype ADD VALUE IF NOT EXISTS 'BREACH_EVAL'")


def downgrade():
    # Cannot reliably remove enum values; no-op on downgrade
    pass
