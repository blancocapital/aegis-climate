"""
Add DRIFT run type

Revision ID: 0010_run_drift_enum
Revises: 0009_rollups_thresholds_breaches
Create Date: 2024-01-01 00:00:10
"""
from alembic import op

revision = "0010_run_drift_enum"
down_revision = "0009_rollups_thresholds_breaches"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE runtype ADD VALUE IF NOT EXISTS 'DRIFT'")


def downgrade():
    # Enum value removal unsafe; no-op
    pass
