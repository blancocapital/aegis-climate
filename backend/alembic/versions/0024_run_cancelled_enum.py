"""
Add cancelled run status

Revision ID: 0024_run_cancelled_enum
Revises: 0023_run_celery_task_id
Create Date: 2024-01-01 00:00:24
"""
from alembic import op

revision = "0024_run_cancelled_enum"
down_revision = "0023_run_celery_task_id"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE runstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")


def downgrade():
    pass
