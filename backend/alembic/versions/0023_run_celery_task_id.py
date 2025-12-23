"""
Add celery task id and cancelled_at to run

Revision ID: 0023_run_celery_task_id
Revises: 0022_run_request_id
Create Date: 2024-01-01 00:00:23
"""
from alembic import op
import sqlalchemy as sa

revision = "0023_run_celery_task_id"
down_revision = "0022_run_request_id"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("run", sa.Column("celery_task_id", sa.String(), nullable=True))
    op.add_column("run", sa.Column("cancelled_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("run", "cancelled_at")
    op.drop_column("run", "celery_task_id")
