"""initial

Revision ID: 0001_initial
Revises: 
Create Date: 2024-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tenant',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    op.create_table(
        'user',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('role', sa.Enum('ADMIN','OPS','ANALYST','AUDITOR','READ_ONLY', name='userrole'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id','email', name='uq_user_tenant_email')
    )

    op.create_table(
        'audit_event',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_event_tenant_created','audit_event',['tenant_id','created_at'], unique=False)

    op.create_table(
        'run',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('run_type', sa.Enum('VALIDATION', name='runtype'), nullable=False),
        sa.Column('status', sa.Enum('QUEUED','RUNNING','SUCCEEDED','FAILED', name='runstatus'), nullable=False),
        sa.Column('config_refs_json', sa.JSON(), nullable=True),
        sa.Column('artifact_checksums_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_run_tenant_created','run',['tenant_id','created_at'], unique=False)

    op.create_table(
        'mapping_template',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('template_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id','name','version', name='uq_mapping_template_version')
    )
    op.create_index('ix_mapping_tenant_created','mapping_template',['tenant_id','created_at'], unique=False)

    op.create_table(
        'exposure_upload',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('object_uri', sa.String(), nullable=False),
        sa.Column('checksum', sa.String(), nullable=False),
        sa.Column('idempotency_key', sa.String(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('mapping_template_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['mapping_template_id'], ['mapping_template.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id','idempotency_key', name='uq_upload_tenant_idempotency')
    )
    op.create_index('ix_upload_tenant_created','exposure_upload',['tenant_id','created_at'], unique=False)

    op.create_table(
        'validation_result',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('upload_id', sa.String(), nullable=False),
        sa.Column('summary_json', sa.JSON(), nullable=False),
        sa.Column('row_errors_uri', sa.String(), nullable=False),
        sa.Column('checksum', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['upload_id'], ['exposure_upload.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_validation_tenant_created','validation_result',['tenant_id','created_at'], unique=False)

    op.create_table(
        'exposure_version',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('upload_id', sa.String(), nullable=True),
        sa.Column('mapping_template_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['mapping_template_id'], ['mapping_template.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['upload_id'], ['exposure_upload.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_exposure_version_tenant_created','exposure_version',['tenant_id','created_at'], unique=False)

    op.create_table(
        'location',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('exposure_version_id', sa.Integer(), nullable=False),
        sa.Column('external_location_id', sa.String(), nullable=False),
        sa.Column('address_line1', sa.String(), nullable=True),
        sa.Column('city', sa.String(), nullable=True),
        sa.Column('country', sa.String(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('tiv', sa.Float(), nullable=True),
        sa.Column('limit', sa.Float(), nullable=True),
        sa.Column('premium', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['exposure_version_id'], ['exposure_version.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id','exposure_version_id','external_location_id', name='uq_location_unique')
    )
    op.create_index('ix_location_tenant_created','location',['tenant_id','created_at'], unique=False)


def downgrade():
    op.drop_index('ix_location_tenant_created', table_name='location')
    op.drop_table('location')
    op.drop_index('ix_exposure_version_tenant_created', table_name='exposure_version')
    op.drop_table('exposure_version')
    op.drop_index('ix_validation_tenant_created', table_name='validation_result')
    op.drop_table('validation_result')
    op.drop_index('ix_upload_tenant_created', table_name='exposure_upload')
    op.drop_table('exposure_upload')
    op.drop_index('ix_mapping_tenant_created', table_name='mapping_template')
    op.drop_table('mapping_template')
    op.drop_index('ix_run_tenant_created', table_name='run')
    op.drop_table('run')
    op.drop_index('ix_audit_event_tenant_created', table_name='audit_event')
    op.drop_table('audit_event')
    op.drop_table('user')
    op.drop_table('tenant')
    op.execute('DROP TYPE IF EXISTS userrole')
    op.execute('DROP TYPE IF EXISTS runstatus')
    op.execute('DROP TYPE IF EXISTS runtype')
