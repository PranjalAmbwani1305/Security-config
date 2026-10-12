"""core grc entities

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa
import app.db.types


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "engagements", "assessments", "assessment_results", "evidence",
    "findings", "risks", "remediations", "webhooks",
]


def upgrade() -> None:
    op.create_table('engagements',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('client_name', sa.String(length=200), nullable=False),
    sa.Column('technology', sa.String(length=120), nullable=False),
    sa.Column('reviewer', sa.String(length=200), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', app.db.types.UTCDateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'code'),
    sa.UniqueConstraint('organization_id', 'id')
    )
    op.create_index(op.f('ix_engagements_organization_id'), 'engagements', ['organization_id'], unique=False)
    op.create_table('webhooks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('url', sa.String(length=2048), nullable=False),
    sa.Column('event', sa.String(length=64), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('last_delivery', app.db.types.UTCDateTime(timezone=True), nullable=True),
    sa.Column('last_status', sa.String(length=64), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', app.db.types.UTCDateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'code')
    )
    op.create_index(op.f('ix_webhooks_organization_id'), 'webhooks', ['organization_id'], unique=False)
    op.create_table('assessments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('engagement_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('created_at', app.db.types.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_at', app.db.types.UTCDateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.ForeignKeyConstraint(['organization_id', 'engagement_id'], ['engagements.organization_id', 'engagements.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('engagement_id'),
    sa.UniqueConstraint('organization_id', 'id')
    )
    op.create_index(op.f('ix_assessments_organization_id'), 'assessments', ['organization_id'], unique=False)
    op.create_table('evidence',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('engagement_id', sa.Uuid(), nullable=False),
    sa.Column('item_id', sa.String(length=64), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('filename', sa.String(length=255), nullable=True),
    sa.Column('content_type', sa.String(length=120), nullable=True),
    sa.Column('size_bytes', sa.Integer(), nullable=True),
    sa.Column('sha256', sa.String(length=64), nullable=True),
    sa.Column('storage_key', sa.String(length=512), nullable=True),
    sa.Column('review_status', sa.String(length=24), nullable=False),
    sa.Column('uploaded_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', app.db.types.UTCDateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id', 'engagement_id'], ['engagements.organization_id', 'engagements.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_evidence_engagement', 'evidence', ['engagement_id'], unique=False)
    op.create_index(op.f('ix_evidence_organization_id'), 'evidence', ['organization_id'], unique=False)
    op.create_table('findings',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('engagement_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('item_id', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('severity', sa.String(length=24), nullable=False),
    sa.Column('recommendation', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('ai_generated', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', app.db.types.UTCDateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['organization_id', 'engagement_id'], ['engagements.organization_id', 'engagements.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'code'),
    sa.UniqueConstraint('organization_id', 'id')
    )
    op.create_index('ix_findings_engagement', 'findings', ['engagement_id'], unique=False)
    op.create_index(op.f('ix_findings_organization_id'), 'findings', ['organization_id'], unique=False)
    op.create_table('assessment_results',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('assessment_id', sa.Uuid(), nullable=False),
    sa.Column('item_id', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=40), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('updated_at', app.db.types.UTCDateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id', 'assessment_id'], ['assessments.organization_id', 'assessments.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('assessment_id', 'item_id')
    )
    op.create_index(op.f('ix_assessment_results_organization_id'), 'assessment_results', ['organization_id'], unique=False)
    op.create_table('remediations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('finding_id', sa.Uuid(), nullable=False),
    sa.Column('action', sa.Text(), nullable=False),
    sa.Column('owner', sa.String(length=200), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=24), nullable=False),
    sa.Column('ai_generated', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', app.db.types.UTCDateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['organization_id', 'finding_id'], ['findings.organization_id', 'findings.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_remediations_finding', 'remediations', ['finding_id'], unique=False)
    op.create_index(op.f('ix_remediations_organization_id'), 'remediations', ['organization_id'], unique=False)
    op.create_table('risks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('engagement_id', sa.Uuid(), nullable=False),
    sa.Column('finding_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('likelihood', sa.Integer(), nullable=False),
    sa.Column('impact', sa.Integer(), nullable=False),
    sa.Column('risk_score', sa.Integer(), nullable=False),
    sa.Column('risk_level', sa.String(length=16), nullable=False),
    sa.Column('treatment', sa.String(length=64), nullable=False),
    sa.Column('owner', sa.String(length=200), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', app.db.types.UTCDateTime(timezone=True), nullable=False),
    sa.CheckConstraint('impact BETWEEN 1 AND 5', name='ck_risk_impact'),
    sa.CheckConstraint('likelihood BETWEEN 1 AND 5', name='ck_risk_likelihood'),
    sa.CheckConstraint('risk_score = likelihood * impact', name='ck_risk_score'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['organization_id', 'engagement_id'], ['engagements.organization_id', 'engagements.id'], ),
    sa.ForeignKeyConstraint(['organization_id', 'finding_id'], ['findings.organization_id', 'findings.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'code')
    )
    op.create_index('ix_risks_engagement', 'risks', ['engagement_id'], unique=False)
    op.create_index(op.f('ix_risks_organization_id'), 'risks', ['organization_id'], unique=False)


    # Row-level security: defence in depth behind the application's own tenant filters.
    # A row is visible/writable only when organization_id equals the per-transaction
    # setting app.current_org (set by the API after authentication). With the setting
    # absent, NO rows are visible. FORCE applies the policy to the table owner too;
    # the application must connect as a non-superuser role without BYPASSRLS.
    if op.get_bind().dialect.name == "postgresql":
        for table in TENANT_TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation ON {table} "
                f"USING (organization_id = NULLIF(current_setting('app.current_org', true), '')::uuid) "
                f"WITH CHECK (organization_id = NULLIF(current_setting('app.current_org', true), '')::uuid)"
            )


def downgrade() -> None:
    op.drop_index(op.f('ix_risks_organization_id'), table_name='risks')
    op.drop_index('ix_risks_engagement', table_name='risks')
    op.drop_table('risks')
    op.drop_index(op.f('ix_remediations_organization_id'), table_name='remediations')
    op.drop_index('ix_remediations_finding', table_name='remediations')
    op.drop_table('remediations')
    op.drop_index(op.f('ix_assessment_results_organization_id'), table_name='assessment_results')
    op.drop_table('assessment_results')
    op.drop_index(op.f('ix_findings_organization_id'), table_name='findings')
    op.drop_index('ix_findings_engagement', table_name='findings')
    op.drop_table('findings')
    op.drop_index(op.f('ix_evidence_organization_id'), table_name='evidence')
    op.drop_index('ix_evidence_engagement', table_name='evidence')
    op.drop_table('evidence')
    op.drop_index(op.f('ix_assessments_organization_id'), table_name='assessments')
    op.drop_table('assessments')
    op.drop_index(op.f('ix_webhooks_organization_id'), table_name='webhooks')
    op.drop_table('webhooks')
    op.drop_index(op.f('ix_engagements_organization_id'), table_name='engagements')
    op.drop_table('engagements')
