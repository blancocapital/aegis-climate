"""rollup and breach tables

Revision ID: 0009_rollups_thresholds_breaches
Revises: 0008_run_rollup_breach_enum
Create Date: 2024-01-01 00:00:09
"""
from alembic import op
import sqlalchemy as sa

revision = '0009_rollups_thresholds_breaches'
down_revision = '0008_run_rollup_breach_enum'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'rollup_config',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('dimensions_json', sa.JSON(), nullable=False),
        sa.Column('filters_json', sa.JSON(), nullable=True),
        sa.Column('measures_json', sa.JSON(), nullable=False),
        sa.Column('created_by', sa.String(), sa.ForeignKey('user.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('tenant_id', 'name', 'version', name='uq_rollup_config_version')
    )
    op.create_index('ix_rollup_config_tenant_created', 'rollup_config', ['tenant_id', 'created_at'], unique=False)

    op.create_table(
        'rollup_result',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('exposure_version_id', sa.Integer(), sa.ForeignKey('exposure_version.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rollup_config_id', sa.Integer(), sa.ForeignKey('rollup_config.id', ondelete='CASCADE'), nullable=False),
        sa.Column('hazard_overlay_result_ids_json', sa.JSON(), nullable=True),
        sa.Column('storage_uri', sa.String(), nullable=True),
        sa.Column('checksum', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('run.id', ondelete='SET NULL')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_rollup_result_tenant_created', 'rollup_result', ['tenant_id', 'created_at'], unique=False)

    op.create_table(
        'rollup_result_item',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('rollup_result_id', sa.Integer(), sa.ForeignKey('rollup_result.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rollup_key_json', sa.JSON(), nullable=False),
        sa.Column('rollup_key_hash', sa.String(), nullable=False),
        sa.Column('metrics_json', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_rollup_item_tenant_result', 'rollup_result_item', ['tenant_id', 'rollup_result_id'], unique=False)
    op.create_unique_constraint('uq_rollup_item_unique', 'rollup_result_item', ['tenant_id', 'rollup_result_id', 'rollup_key_hash'])

    op.create_table(
        'threshold_rule',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('rule_json', sa.JSON(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.String(), sa.ForeignKey('user.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_threshold_rule_tenant_created', 'threshold_rule', ['tenant_id', 'created_at'], unique=False)

    op.create_table(
        'breach',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('exposure_version_id', sa.Integer(), sa.ForeignKey('exposure_version.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rollup_result_id', sa.Integer(), sa.ForeignKey('rollup_result.id', ondelete='CASCADE'), nullable=False),
        sa.Column('threshold_rule_id', sa.Integer(), sa.ForeignKey('threshold_rule.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rollup_key_json', sa.JSON(), nullable=False),
        sa.Column('rollup_key_hash', sa.String(), nullable=False),
        sa.Column('metric_name', sa.String(), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('threshold_value', sa.Float(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('last_eval_run_id', sa.Integer(), sa.ForeignKey('run.id', ondelete='SET NULL')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_breach_tenant_status_last_seen', 'breach', ['tenant_id', 'status', 'last_seen_at'], unique=False)
    op.create_unique_constraint('uq_breach_unique', 'breach', ['tenant_id', 'threshold_rule_id', 'exposure_version_id', 'rollup_key_hash'])


def downgrade():
    op.drop_constraint('uq_breach_unique', 'breach', type_='unique')
    op.drop_index('ix_breach_tenant_status_last_seen', table_name='breach')
    op.drop_table('breach')
    op.drop_index('ix_threshold_rule_tenant_created', table_name='threshold_rule')
    op.drop_table('threshold_rule')
    op.drop_constraint('uq_rollup_item_unique', 'rollup_result_item', type_='unique')
    op.drop_index('ix_rollup_item_tenant_result', table_name='rollup_result_item')
    op.drop_table('rollup_result_item')
    op.drop_index('ix_rollup_result_tenant_created', table_name='rollup_result')
    op.drop_table('rollup_result')
    op.drop_index('ix_rollup_config_tenant_created', table_name='rollup_config')
    op.drop_table('rollup_config')
