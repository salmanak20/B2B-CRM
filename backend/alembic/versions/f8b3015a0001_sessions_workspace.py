"""Add server sessions and workspace operations without replacing business rows.

Revision ID: f8b3015a0001
Revises: 0aa836556f2a
"""
from alembic import op
import sqlalchemy as sa

revision="f8b3015a0001"
down_revision="0aa836556f2a"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("deals",sa.Column("closed_at",sa.DateTime(timezone=True),nullable=True))
    op.create_index("ix_deals_closed_at","deals",["closed_at"])
    op.add_column("users",sa.Column("auth_user_id",sa.String(36),nullable=True))
    op.add_column("users",sa.Column("preferences",sa.JSON(),nullable=False,server_default='{}'))
    op.create_index("uq_users_auth_user_id","users",["auth_user_id"],unique=True)
    op.create_table("auth_sessions",sa.Column("id",sa.String(64),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("access_expires_at",sa.DateTime(timezone=True)),sa.Column("access_token",sa.Text()),sa.Column("refresh_token",sa.Text()),sa.Column("recovery",sa.Boolean(),nullable=False,server_default=sa.false()))
    op.create_index("ix_auth_sessions_user_id","auth_sessions",["user_id"])
    op.create_index("ix_auth_sessions_expires_at","auth_sessions",["expires_at"])
    op.create_table("rate_buckets",sa.Column("id",sa.String(64),primary_key=True),sa.Column("count",sa.Integer(),nullable=False),sa.Column("window_start",sa.DateTime(timezone=True),nullable=False))
    op.create_table("workspace_settings",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("name",sa.String(100),nullable=False),sa.Column("timezone",sa.String(100),nullable=False),sa.Column("currency",sa.String(3),nullable=False))
    op.create_table("workflow_rules",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("name",sa.String(100),nullable=False),sa.Column("owner_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),sa.Column("trigger_status",sa.String(30),nullable=False),sa.Column("min_value",sa.Numeric(15,2),nullable=False),sa.Column("assigned_to_id",sa.Integer(),sa.ForeignKey("users.id")),sa.Column("task_title",sa.String(255),nullable=False),sa.Column("enabled",sa.Boolean(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_table("workflow_runs",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("rule_id",sa.Integer(),sa.ForeignKey("workflow_rules.id",ondelete="CASCADE"),nullable=False),sa.Column("lead_id",sa.Integer(),sa.ForeignKey("leads.id",ondelete="CASCADE"),nullable=False),sa.Column("task_id",sa.Integer(),sa.ForeignKey("tasks.id",ondelete="SET NULL")),sa.UniqueConstraint("rule_id","lead_id",name="uq_workflow_lead_once"))
    op.create_table("attachments",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("entity",sa.String(30),nullable=False),sa.Column("entity_id",sa.Integer(),nullable=False),sa.Column("uploaded_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),sa.Column("name",sa.String(255),nullable=False),sa.Column("storage_path",sa.Text(),unique=True,nullable=False),sa.Column("content_type",sa.String(100),nullable=False),sa.Column("size",sa.Integer(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_attachments_entity","attachments",["entity"])
    op.create_index("ix_attachments_entity_id","attachments",["entity_id"])
    op.create_table("notification_events",sa.Column("id",sa.String(64),primary_key=True),sa.Column("task_id",sa.Integer(),sa.ForeignKey("tasks.id",ondelete="CASCADE"),nullable=False))
    op.create_index("ix_notification_events_task_id","notification_events",["task_id"])
    if op.get_bind().dialect.name=="postgresql":
        # Browser clients have no direct table access. The trusted backend connects as
        # the table owner/BYPASSRLS role and enforces the existing workspace RBAC.
        tables=["alembic_version","users","roles","permissions","role_permissions","companies","contacts","leads","deals","pipelines","pipeline_stages","tasks","activities","notifications","audit_logs","auth_sessions","rate_buckets","workspace_settings","workflow_rules","workflow_runs","attachments","notification_events"]
        for table in tables:
            # Catalog checks run in PostgreSQL, so offline SQL generation is safe.
            op.execute(sa.text(f'''DO $crm$ BEGIN
                IF to_regclass('public.{table}') IS NOT NULL THEN
                    ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY;
                    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
                        REVOKE ALL ON TABLE public."{table}" FROM anon;
                    END IF;
                    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
                        REVOKE ALL ON TABLE public."{table}" FROM authenticated;
                    END IF;
                END IF;
            END $crm$'''))

def downgrade():
    for table in ["notification_events","attachments","workflow_runs","workflow_rules","workspace_settings","rate_buckets","auth_sessions"]:
        op.drop_table(table)
    op.drop_index("uq_users_auth_user_id",table_name="users")
    op.drop_column("users","preferences")
    op.drop_column("users","auth_user_id")
    op.drop_index("ix_deals_closed_at",table_name="deals")
    op.drop_column("deals","closed_at")
