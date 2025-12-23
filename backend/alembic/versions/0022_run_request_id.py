"""
Add request_id to run

Revision ID: 0022_run_request_id
Revises: 0021_res_score_request_fp
Create Date: 2024-01-01 00:00:22
"""
from alembic import op
import sqlalchemy as sa

revision = "0022_run_request_id"
down_revision = "0021_res_score_request_fp"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("run", sa.Column("request_id", sa.String(), nullable=True))
    op.create_index("ix_run_tenant_request", "run", ["tenant_id", "request_id"])


def downgrade():
    op.drop_index("ix_run_tenant_request", table_name="run")
    op.drop_column("run", "request_id")
