"""Phase 1A: nullable organizations and membership foundation; no data assignment.

Revision ID: a1b2c3d4e501
Revises: f8b3015a0001
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e501"
down_revision = "f8b3015a0001"
branch_labels = None
depends_on = None

TENANT_TABLES = ['companies',
 'contacts',
 'leads',
 'pipelines',
 'pipeline_stages',
 'deals',
 'tasks',
 'activities',
 'workspace_settings',
 'workflow_rules',
 'workflow_runs',
 'notifications',
 'attachments',
 'audit_logs',
 'notification_events']
CRM_REFERENCES = {'contacts': {'company_id': 'companies'},
 'leads': {'company_id': 'companies', 'contact_id': 'contacts'},
 'deals': {'company_id': 'companies',
           'contact_id': 'contacts',
           'lead_id': 'leads',
           'pipeline_id': 'pipelines',
           'stage_id': 'pipeline_stages'},
 'pipeline_stages': {'pipeline_id': 'pipelines'},
 'tasks': {'company_id': 'companies',
           'contact_id': 'contacts',
           'lead_id': 'leads',
           'deal_id': 'deals'},
 'activities': {'company_id': 'companies',
                'contact_id': 'contacts',
                'lead_id': 'leads',
                'deal_id': 'deals'},
 'workflow_runs': {'rule_id': 'workflow_rules', 'lead_id': 'leads', 'task_id': 'tasks'},
 'notification_events': {'task_id': 'tasks'}}
MEMBER_REFERENCES = {'companies': ('owner_id',),
 'contacts': ('owner_id',),
 'leads': ('owner_id',),
 'deals': ('owner_id',),
 'tasks': ('owner_id', 'assigned_to_id'),
 'activities': ('user_id',),
 'notifications': ('user_id',),
 'audit_logs': ('user_id',),
 'workflow_rules': ('owner_id', 'assigned_to_id'),
 'attachments': ('uploaded_by',)}


def upgrade():
    op.create_table("organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"))
    op.create_table("memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("permission_role_name", sa.String(50), sa.ForeignKey("roles.name"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_memberships_organization_user"),
        sa.CheckConstraint("role IN ('owner','admin','sales_manager','sales_rep','viewer')", name="ck_memberships_role"),
        sa.CheckConstraint("(role = 'owner' AND permission_role_name = 'admin') OR (role <> 'owner' AND permission_role_name = role)", name="ck_memberships_permission_role"))
    op.create_index("ix_memberships_organization_id", "memberships", ["organization_id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    for table in TENANT_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(f"fk_{table}_organization", "organizations", ["organization_id"], ["id"])
            batch.create_unique_constraint(f"uq_{table}_organization_id", ["organization_id", "id"])
            batch.create_index(f"ix_{table}_organization_id", ["organization_id"])
    for table in TENANT_TABLES:
        with op.batch_alter_table(table) as batch:
            for column, target in CRM_REFERENCES.get(table, {}).items():
                batch.create_foreign_key(f"fk_{table}_org_{column}", target,
                    ["organization_id", column], ["organization_id", "id"], deferrable=True, initially="DEFERRED")
                batch.create_index(f"ix_{table}_org_{column}", ["organization_id", column])
            for column in MEMBER_REFERENCES.get(table, ()):
                batch.create_foreign_key(f"fk_{table}_member_{column}", "memberships",
                    ["organization_id", column], ["organization_id", "user_id"], deferrable=True, initially="DEFERRED")
                batch.create_index(f"ix_{table}_org_{column}", ["organization_id", column])
    with op.batch_alter_table("workspace_settings") as batch:
        batch.create_unique_constraint("uq_workspace_settings_organization", ["organization_id"])
    with op.batch_alter_table("pipelines") as batch:
        batch.drop_index("ix_pipelines_name")
        batch.create_index("ix_pipelines_name", ["name"], unique=False)
        batch.create_unique_constraint("uq_pipelines_organization_name", ["organization_id", "name"])
        batch.create_index("uq_pipelines_legacy_name", ["name"], unique=True,
                           postgresql_where=sa.text("organization_id IS NULL"),
                           sqlite_where=sa.text("organization_id IS NULL"))
    if op.get_bind().dialect.name == "postgresql":
        # Match the existing default-deny Data API posture; access stays disabled.
        for table in ("organizations", "memberships"):
            op.execute(sa.text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'REVOKE ALL ON TABLE public."{table}" FROM PUBLIC'))
            for role in ("anon", "authenticated"):
                op.execute(sa.text(f"DO $tenant$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN REVOKE ALL ON TABLE public.\"{table}\" FROM {role}; END IF; END $tenant$"))


def downgrade():
    # Refuse to discard organization assignments once provisioning has begun.
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM organizations)")) or bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM memberships)")):
        raise RuntimeError("Refusing tenant downgrade: preserve organization/membership data before rollback")
    for table in reversed(TENANT_TABLES):
        with op.batch_alter_table(table) as batch:
            for column in MEMBER_REFERENCES.get(table, ()):
                batch.drop_constraint(f"fk_{table}_member_{column}", type_="foreignkey")
                batch.drop_index(f"ix_{table}_org_{column}")
            for column in CRM_REFERENCES.get(table, {}):
                batch.drop_constraint(f"fk_{table}_org_{column}", type_="foreignkey")
                batch.drop_index(f"ix_{table}_org_{column}")
    with op.batch_alter_table("pipelines") as batch:
        batch.drop_constraint("uq_pipelines_organization_name", type_="unique")
        batch.drop_index("uq_pipelines_legacy_name")
        batch.drop_index("ix_pipelines_name")
        batch.create_index("ix_pipelines_name", ["name"], unique=True)
    with op.batch_alter_table("workspace_settings") as batch:
        batch.drop_constraint("uq_workspace_settings_organization", type_="unique")
    for table in reversed(TENANT_TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_organization_id")
            batch.drop_constraint(f"fk_{table}_organization", type_="foreignkey")
            batch.drop_constraint(f"uq_{table}_organization_id", type_="unique")
            batch.drop_column("organization_id")
    op.drop_table("memberships")
    op.drop_table("organizations")
