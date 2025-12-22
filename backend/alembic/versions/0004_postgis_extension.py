"""ensure postgis extension

Revision ID: 0004_postgis_extension
Revises: 0003_geocode_quality
Create Date: 2024-05-02
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0004_postgis_extension"
down_revision: Union[str, None] = "0003_geocode_quality"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    # keep extension if already installed to avoid breaking deps
    pass
