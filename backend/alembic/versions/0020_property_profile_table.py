"""
Add property profile table

Revision ID: 0020_property_profile_table
Revises: 0019_property_enrich_enum
Create Date: 2024-01-01 00:00:20
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_property_profile_table"
down_revision = "0019_property_enrich_enum"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "property_profile",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("location.id", ondelete="SET NULL"), nullable=True),
        sa.Column("address_fingerprint", sa.String(), nullable=False),
        sa.Column("standardized_address_json", sa.JSON(), nullable=True),
        sa.Column("geocode_json", sa.JSON(), nullable=True),
        sa.Column("parcel_json", sa.JSON(), nullable=True),
        sa.Column("characteristics_json", sa.JSON(), nullable=True),
        sa.Column("structural_json", sa.JSON(), nullable=True),
        sa.Column("provenance_json", sa.JSON(), nullable=True),
        sa.Column("code_version", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "address_fingerprint", name="uq_property_profile_fingerprint"),
    )
    op.create_index(
        "ix_property_profile_tenant_updated",
        "property_profile",
        ["tenant_id", "updated_at"],
    )


def downgrade():
    op.drop_index("ix_property_profile_tenant_updated", table_name="property_profile")
    op.drop_table("property_profile")
