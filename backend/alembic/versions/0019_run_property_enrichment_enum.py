"""
Add property enrichment run type

Revision ID: 0019_run_property_enrichment_enum
Revises: 0018_resilience_hazard_versions_lineage
Create Date: 2024-01-01 00:00:19
"""
from alembic import op

revision = "0019_run_property_enrichment_enum"
down_revision = "0018_resilience_hazard_versions_lineage"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE runtype ADD VALUE IF NOT EXISTS 'PROPERTY_ENRICHMENT'")


def downgrade():
    pass
