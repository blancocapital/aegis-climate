"""
Add hazard versions lineage to resilience results

Revision ID: 0018_resilience_hazard_versions_lineage
Revises: 0017_resilience_scoring_version
Create Date: 2024-01-01 00:00:18
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_resilience_hazard_versions_lineage"
down_revision = "0017_resilience_scoring_version"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("resilience_score_result", sa.Column("hazard_versions_json", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("resilience_score_result", "hazard_versions_json")
