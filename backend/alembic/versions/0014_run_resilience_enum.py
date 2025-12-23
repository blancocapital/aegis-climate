"""
Add resilience score run type

Revision ID: 0014_run_resilience_enum
Revises: 0013_hazard_feature_indexes
Create Date: 2024-01-01 00:00:14
"""
from alembic import op

revision = "0014_run_resilience_enum"
down_revision = "0013_hazard_feature_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE runtype ADD VALUE IF NOT EXISTS 'RESILIENCE_SCORE'")


def downgrade():
    pass
