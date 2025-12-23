"""
Add policy link to resilience score results

Revision ID: 0026_res_policy_link
Revises: 0025_policy_packs
Create Date: 2024-01-01 00:00:26
"""
from alembic import op
import sqlalchemy as sa

revision = "0026_res_policy_link"
down_revision = "0025_policy_packs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "resilience_score_result",
        sa.Column("policy_pack_version_id", sa.Integer(), sa.ForeignKey("policy_pack_version.id", ondelete="SET NULL")),
    )
    op.add_column(
        "resilience_score_result",
        sa.Column("policy_used_json", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_resilience_score_result_policy",
        "resilience_score_result",
        ["tenant_id", "policy_pack_version_id"],
    )


def downgrade():
    op.drop_index("ix_resilience_score_result_policy", table_name="resilience_score_result")
    op.drop_column("resilience_score_result", "policy_used_json")
    op.drop_column("resilience_score_result", "policy_pack_version_id")
