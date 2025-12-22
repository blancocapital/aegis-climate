"""geocode and quality fields

Revision ID: 0003_geocode_quality
Revises: 0002_run_governance
Create Date: 2024-05-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003_geocode_quality"
down_revision: Union[str, None] = "0002_run_governance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("location", sa.Column("geocode_method", sa.String(), nullable=True))
    op.add_column("location", sa.Column("geocode_confidence", sa.Float(), nullable=True))
    op.add_column("location", sa.Column("quality_tier", sa.String(), nullable=True))
    op.add_column("location", sa.Column("quality_reasons_json", sa.JSON(), nullable=True))
    op.add_column("location", sa.Column("updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("location", "updated_at")
    op.drop_column("location", "quality_reasons_json")
    op.drop_column("location", "quality_tier")
    op.drop_column("location", "geocode_confidence")
    op.drop_column("location", "geocode_method")
