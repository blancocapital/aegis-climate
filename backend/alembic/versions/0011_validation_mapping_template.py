"""
Add mapping_template_id to validation_result

Revision ID: 0011_validation_mapping_template
Revises: 0010_run_drift_enum
Create Date: 2024-01-01 00:00:11
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_validation_mapping_template"
down_revision = "0010_run_drift_enum"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "validation_result",
        sa.Column(
            "mapping_template_id",
            sa.Integer(),
            sa.ForeignKey("mapping_template.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("validation_result", "mapping_template_id")
