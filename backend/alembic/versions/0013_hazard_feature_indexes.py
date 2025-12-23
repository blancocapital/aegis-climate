"""
Add hazard feature polygon indexes

Revision ID: 0013_hazard_feature_indexes
Revises: 0012_drift_tables
Create Date: 2024-01-01 00:00:13
"""
from alembic import op

revision = "0013_hazard_feature_indexes"
down_revision = "0012_drift_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_hazard_feature_polygon_geom_gist",
        "hazard_feature_polygon",
        ["geom"],
        postgresql_using="gist",
    )
    op.create_index(
        "ix_hazard_feature_polygon_tenant_version",
        "hazard_feature_polygon",
        ["tenant_id", "hazard_dataset_version_id"],
    )


def downgrade():
    op.drop_index("ix_hazard_feature_polygon_tenant_version", table_name="hazard_feature_polygon")
    op.drop_index("ix_hazard_feature_polygon_geom_gist", table_name="hazard_feature_polygon")
