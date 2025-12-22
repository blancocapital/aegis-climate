"""add overlay run type

Revision ID: 0006_run_overlay_enum
Revises: 0005_exposure_contract_fields
Create Date: 2024-05-02
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0006_run_overlay_enum"
down_revision: Union[str, None] = "0005_exposure_contract_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE runtype ADD VALUE IF NOT EXISTS 'OVERLAY'")


def downgrade() -> None:
    # enum contraction avoided for safety
    pass
