"""Private signup intents and atomic workspace provisioning receipts."""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e504"
down_revision = "a1b2c3d4e503"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("signup_intents",
        sa.Column("provider_user_id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(100), nullable=False))
    op.create_table("organization_provisions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("organization_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False, unique=True),
        sa.UniqueConstraint("user_id", "request_key", name="uq_provision_user_request"))
    if op.get_bind().dialect.name == "postgresql":
        for table in ("signup_intents", "organization_provisions"):
            op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
            op.execute(f'REVOKE ALL ON {table} FROM PUBLIC')
            for role in ("anon", "authenticated"):
                if op.get_bind().execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}).scalar():
                    op.execute(f'REVOKE ALL ON {table} FROM {role}')


def downgrade():
    for table in ("organization_provisions", "signup_intents"):
        if op.get_bind().execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError("Refusing to remove populated onboarding history")
    op.drop_table("organization_provisions")
    op.drop_table("signup_intents")
