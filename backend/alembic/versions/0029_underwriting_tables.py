"""
Add underwriting rules, findings, notes, decisions, and exception triage

Revision ID: 0029_underwriting_tables
Revises: 0028_run_uw_eval_enum
Create Date: 2025-01-01 00:00:29
"""
import sqlalchemy as sa
from alembic import op

revision = "0029_underwriting_tables"
down_revision = "0028_run_uw_eval_enum"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "uw_rule",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("target", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("rule_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), sa.ForeignKey("user.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_uw_rule_tenant_created", "uw_rule", ["tenant_id", "created_at"])

    op.create_table(
        "uw_finding",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "exposure_version_id",
            sa.Integer(),
            sa.ForeignKey("exposure_version.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("location.id", ondelete="CASCADE"), nullable=True),
        sa.Column(
            "rollup_result_id",
            sa.Integer(),
            sa.ForeignKey("rollup_result.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("rollup_key_hash", sa.String(), nullable=True),
        sa.Column("uw_rule_id", sa.Integer(), sa.ForeignKey("uw_rule.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("disposition", sa.String(), nullable=False),
        sa.Column("explanation_json", sa.JSON(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("last_eval_run_id", sa.Integer(), sa.ForeignKey("run.id", ondelete="SET NULL")),
    )
    op.create_index(
        "ix_uw_finding_tenant_status_last_seen",
        "uw_finding",
        ["tenant_id", "status", "last_seen_at"],
    )
    op.create_index(
        "ix_uw_finding_tenant_exposure",
        "uw_finding",
        ["tenant_id", "exposure_version_id"],
    )
    op.create_index(
        "ix_uw_finding_tenant_rule",
        "uw_finding",
        ["tenant_id", "uw_rule_id"],
    )
    op.create_index(
        "uq_uw_finding_location",
        "uw_finding",
        ["tenant_id", "uw_rule_id", "exposure_version_id", "location_id"],
        unique=True,
        postgresql_where=sa.text("location_id IS NOT NULL"),
    )
    op.create_index(
        "uq_uw_finding_rollup",
        "uw_finding",
        ["tenant_id", "uw_rule_id", "exposure_version_id", "rollup_key_hash"],
        unique=True,
        postgresql_where=sa.text("rollup_key_hash IS NOT NULL"),
    )

    op.create_table(
        "uw_note",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(), sa.ForeignKey("user.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_uw_note_tenant_entity", "uw_note", ["tenant_id", "entity_type", "entity_id"])
    op.create_index("ix_uw_note_tenant_created", "uw_note", ["tenant_id", "created_at"])

    op.create_table(
        "uw_decision",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "exposure_version_id",
            sa.Integer(),
            sa.ForeignKey("exposure_version.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("conditions_json", sa.JSON(), nullable=True),
        sa.Column("rationale_text", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(), sa.ForeignKey("user.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "exposure_version_id", name="uq_uw_decision_exposure"),
    )
    op.create_index("ix_uw_decision_tenant_created", "uw_decision", ["tenant_id", "created_at"])

    op.create_table(
        "exception_triage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "exposure_version_id",
            sa.Integer(),
            sa.ForeignKey("exposure_version.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("exception_key", sa.String(), nullable=False),
        sa.Column("exception_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "exception_key", name="uq_exception_triage_key"),
    )
    op.create_index("ix_exception_triage_tenant_status", "exception_triage", ["tenant_id", "status"])
    op.create_index("ix_exception_triage_tenant_exposure", "exception_triage", ["tenant_id", "exposure_version_id"])


def downgrade():
    op.drop_index("ix_exception_triage_tenant_exposure", table_name="exception_triage")
    op.drop_index("ix_exception_triage_tenant_status", table_name="exception_triage")
    op.drop_table("exception_triage")

    op.drop_index("ix_uw_decision_tenant_created", table_name="uw_decision")
    op.drop_table("uw_decision")

    op.drop_index("ix_uw_note_tenant_created", table_name="uw_note")
    op.drop_index("ix_uw_note_tenant_entity", table_name="uw_note")
    op.drop_table("uw_note")

    op.drop_index("uq_uw_finding_rollup", table_name="uw_finding")
    op.drop_index("uq_uw_finding_location", table_name="uw_finding")
    op.drop_index("ix_uw_finding_tenant_rule", table_name="uw_finding")
    op.drop_index("ix_uw_finding_tenant_exposure", table_name="uw_finding")
    op.drop_index("ix_uw_finding_tenant_status_last_seen", table_name="uw_finding")
    op.drop_table("uw_finding")

    op.drop_index("ix_uw_rule_tenant_created", table_name="uw_rule")
    op.drop_table("uw_rule")
