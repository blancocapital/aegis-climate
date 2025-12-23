"""
Add scoring version and code version to resilience results

Revision ID: 0017_resilience_scoring_version
Revises: 0016_location_structural_json
Create Date: 2024-01-01 00:00:17
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_resilience_scoring_version"
down_revision = "0016_location_structural_json"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "resilience_score_result",
        sa.Column("scoring_version", sa.String(), nullable=False, server_default="v1"),
    )
    op.add_column("resilience_score_result", sa.Column("code_version", sa.String(), nullable=True))
    op.execute("UPDATE resilience_score_result SET scoring_version = 'v1' WHERE scoring_version IS NULL")


def downgrade():
    op.drop_column("resilience_score_result", "code_version")
    op.drop_column("resilience_score_result", "scoring_version")
