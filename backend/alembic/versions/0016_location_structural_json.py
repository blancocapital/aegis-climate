"""
Add structural attributes to location

Revision ID: 0016_location_structural_json
Revises: 0015_resilience_score_tables
Create Date: 2024-01-01 00:00:16
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_location_structural_json"
down_revision = "0015_resilience_score_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("location", sa.Column("structural_json", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("location", "structural_json")
