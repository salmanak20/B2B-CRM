"""Phase 3: pending invitations and non-destructive membership removal."""
from alembic import op
import sqlalchemy as sa

revision="a1b2c3d4e503"
down_revision="a1b2c3d4e502"
branch_labels=None
depends_on=None


def upgrade():
    op.add_column("memberships",sa.Column("removed_at",sa.DateTime(timezone=True),nullable=True))
    op.create_table("organization_invitations",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",name="fk_organization_invitations_organization"),nullable=True),
        sa.Column("email",sa.String(255),nullable=False),sa.Column("name",sa.String(100),nullable=False),
        sa.Column("role",sa.String(50),nullable=False),sa.Column("status",sa.String(20),nullable=False),
        sa.Column("invited_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("provider_user_id",sa.String(36),nullable=False),
        sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("organization_id","id",name="uq_organization_invitations_organization_id"),
        sa.UniqueConstraint("organization_id","email",name="uq_org_invitation_email"),
        sa.CheckConstraint("role IN ('owner','admin','sales_manager','sales_rep','viewer')",name="ck_invitation_role"),
        sa.CheckConstraint("status IN ('pending','accepted','revoked')",name="ck_invitation_status"),
        sa.ForeignKeyConstraint(["organization_id","invited_by"],["memberships.organization_id","memberships.user_id"],name="fk_organization_invitations_member_invited_by",deferrable=True,initially="DEFERRED"))
    for columns in (("organization_id",),("email",),("organization_id","invited_by")):
        op.create_index("ix_organization_invitations_"+("org_invited_by" if len(columns)>1 else columns[0]),"organization_invitations",list(columns))
    if op.get_bind().dialect.name=="postgresql":
        op.execute('ALTER TABLE public.organization_invitations ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL ON TABLE public.organization_invitations FROM PUBLIC')
        for role in ("anon","authenticated"):
            op.execute(f"DO $safe$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN REVOKE ALL ON TABLE public.organization_invitations FROM {role}; END IF; END $safe$")


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM organization_invitations)")):
        raise RuntimeError("Refusing to discard invitation history")
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM memberships WHERE removed_at IS NOT NULL)")):
        raise RuntimeError("Refusing to discard membership removal history")
    op.drop_table("organization_invitations")
    op.drop_column("memberships","removed_at")
