"""exposure contract fields and tenant currency

Revision ID: 0005_exposure_contract_fields
Revises: 0004_postgis_extension
Create Date: 2024-05-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005_exposure_contract_fields"
down_revision: Union[str, None] = "0004_postgis_extension"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("default_currency", sa.String(), nullable=False, server_default="USD"))
    op.add_column("location", sa.Column("state_region", sa.String(), nullable=True))
    op.add_column("location", sa.Column("postal_code", sa.String(), nullable=True))
    op.add_column("location", sa.Column("currency", sa.String(), nullable=True))
    op.add_column("location", sa.Column("lob", sa.String(), nullable=True))
    op.add_column("location", sa.Column("product_code", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("location", "product_code")
    op.drop_column("location", "lob")
    op.drop_column("location", "currency")
    op.drop_column("location", "postal_code")
    op.drop_column("location", "state_region")
    op.drop_column("tenant", "default_currency")
