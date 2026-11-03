"""Independent platform permissions and non-destructive organization suspension."""
from alembic import op
import sqlalchemy as sa
revision='a1b2c3d4e505'
down_revision='a1b2c3d4e504'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('organizations',sa.Column('is_suspended',sa.Boolean,nullable=False,server_default=sa.false()))
    op.create_table('platform_administrators',
        sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id'),primary_key=True),
        sa.Column('auth_user_id',sa.String(36),nullable=False),
        sa.Column('is_active',sa.Boolean,nullable=False))
    op.create_table('platform_audit',sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('actor_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('action',sa.String(60),nullable=False),sa.Column('target_id',sa.Integer,nullable=False),
        sa.Column('reason',sa.Text,nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now()))
    if op.get_bind().dialect.name=='postgresql':
        for table in ('platform_administrators','platform_audit'):
            op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
            op.execute(f'REVOKE ALL ON {table} FROM PUBLIC')
            for role in ('anon','authenticated'):
                op.execute(f"DO $safe$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN REVOKE ALL ON {table} FROM {role}; END IF; END $safe$")

def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM platform_administrators) OR EXISTS(SELECT 1 FROM platform_audit) OR EXISTS(SELECT 1 FROM organizations WHERE is_suspended)')):
        raise RuntimeError('Refusing to discard platform administration state')
    op.drop_table('platform_audit');op.drop_table('platform_administrators');op.drop_column('organizations','is_suspended')
