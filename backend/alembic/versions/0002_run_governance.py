"""run governance and idempotency

Revision ID: 0002_run_governance
Revises: 0001_initial
Create Date: 2024-05-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_run_governance"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # extend run_type enum
    op.execute("ALTER TYPE runtype ADD VALUE IF NOT EXISTS 'COMMIT'")
    op.execute("ALTER TYPE runtype ADD VALUE IF NOT EXISTS 'GEOCODE'")

    op.add_column("run", sa.Column("input_refs_json", sa.JSON(), nullable=True))
    op.add_column("run", sa.Column("output_refs_json", sa.JSON(), nullable=True))
    op.add_column("run", sa.Column("code_version", sa.String(), nullable=True))
    op.add_column("run", sa.Column("created_by", sa.String(), nullable=True))
    op.add_column("run", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("run", sa.Column("completed_at", sa.DateTime(), nullable=True))

    op.add_column("exposure_version", sa.Column("idempotency_key", sa.String(), nullable=True))
    op.add_column("mapping_template", sa.Column("created_by", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("mapping_template", "created_by")
    op.drop_column("exposure_version", "idempotency_key")
    op.drop_column("run", "completed_at")
    op.drop_column("run", "started_at")
    op.drop_column("run", "created_by")
    op.drop_column("run", "code_version")
    op.drop_column("run", "output_refs_json")
    op.drop_column("run", "input_refs_json")
    # note: enums not downgraded to keep data safety
