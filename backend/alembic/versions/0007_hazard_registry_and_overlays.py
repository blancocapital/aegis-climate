"""hazard registry and overlay tables

Revision ID: 0007_hazard_registry_and_overlays
Revises: 0006_run_overlay_enum
Create Date: 2024-05-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry


# revision identifiers, used by Alembic.
revision: str = "0007_hazard_registry_and_overlays"
down_revision: Union[str, None] = "0006_run_overlay_enum"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hazard_dataset",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("peril", sa.String(), nullable=False),
        sa.Column("vendor", sa.String(), nullable=True),
        sa.Column("coverage_geo", sa.String(), nullable=True),
        sa.Column("license_ref", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_hazard_dataset_tenant_created", "hazard_dataset", ["tenant_id", "created_at"], unique=False)

    op.create_table(
        "hazard_dataset_version",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("hazard_dataset_id", sa.Integer(), nullable=False),
        sa.Column("version_label", sa.String(), nullable=False),
        sa.Column("storage_uri", sa.String(), nullable=False),
        sa.Column("checksum", sa.String(), nullable=False),
        sa.Column("effective_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hazard_dataset_id"], ["hazard_dataset.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "hazard_dataset_id", "version_label", name="uq_hazard_dataset_version"),
    )
    op.create_index(
        "ix_hazard_dataset_version_tenant_created",
        "hazard_dataset_version",
        ["tenant_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "hazard_feature_polygon",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("hazard_dataset_version_id", sa.Integer(), nullable=False),
        sa.Column("geom", Geometry("MULTIPOLYGON", srid=4326)),
        sa.Column("properties_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hazard_dataset_version_id"], ["hazard_dataset_version.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_hazard_feature_polygon_tenant", "hazard_feature_polygon", ["tenant_id"], unique=False)

    op.create_table(
        "hazard_overlay_result",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("exposure_version_id", sa.Integer(), nullable=False),
        sa.Column("hazard_dataset_version_id", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("params_json", sa.JSON(), nullable=True),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exposure_version_id"], ["exposure_version.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hazard_dataset_version_id"], ["hazard_dataset_version.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["run.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_hazard_overlay_tenant_created", "hazard_overlay_result", ["tenant_id", "created_at"], unique=False)

    op.create_table(
        "location_hazard_attribute",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("hazard_overlay_result_id", sa.Integer(), nullable=False),
        sa.Column("attributes_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["location.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hazard_overlay_result_id"], ["hazard_overlay_result.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_location_hazard_attr_tenant", "location_hazard_attribute", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_location_hazard_attr_tenant", table_name="location_hazard_attribute")
    op.drop_table("location_hazard_attribute")
    op.drop_index("ix_hazard_overlay_tenant_created", table_name="hazard_overlay_result")
    op.drop_table("hazard_overlay_result")
    op.drop_index("ix_hazard_feature_polygon_tenant", table_name="hazard_feature_polygon")
    op.drop_table("hazard_feature_polygon")
    op.drop_index("ix_hazard_dataset_version_tenant_created", table_name="hazard_dataset_version")
    op.drop_table("hazard_dataset_version")
    op.drop_index("ix_hazard_dataset_tenant_created", table_name="hazard_dataset")
    op.drop_table("hazard_dataset")
