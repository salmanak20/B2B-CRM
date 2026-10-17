"""Phase 2: nullable server-side active organization selection; no data migration."""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e502"
down_revision = "a1b2c3d4e501"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("auth_sessions", sa.Column("active_organization_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_auth_sessions_active_organization", "auth_sessions", "organizations",
                          ["active_organization_id"], ["id"])


def downgrade():
    op.drop_constraint("fk_auth_sessions_active_organization", "auth_sessions", type_="foreignkey")
    op.drop_column("auth_sessions", "active_organization_id")
