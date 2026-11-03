"""Subscription metadata only: no plans, prices or assignments are seeded."""
from alembic import op
import sqlalchemy as sa
revision='a1b2c3d4e506'
down_revision='a1b2c3d4e505'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('subscription_plans',sa.Column('id',sa.Integer,primary_key=True),sa.Column('code',sa.String(30),unique=True,nullable=False),
        sa.Column('name',sa.String(100),nullable=False),sa.Column('currency',sa.String(3),nullable=False),sa.Column('price',sa.Numeric(14,2)),
        sa.Column('billing_interval',sa.String(10),nullable=False),sa.Column('entitlements',sa.JSON,nullable=False),sa.Column('seat_limit',sa.Integer),
        sa.Column('published',sa.Boolean,nullable=False),sa.Column('external_price_id',sa.String(255)),
        sa.CheckConstraint('price IS NULL OR price >= 0',name='ck_plan_price'),sa.CheckConstraint('seat_limit IS NULL OR seat_limit > 0',name='ck_plan_seats'))
    op.create_table('subscriptions',sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,sa.ForeignKey('organizations.id'),unique=True,nullable=False),
        sa.Column('plan_id',sa.Integer,sa.ForeignKey('subscription_plans.id'),nullable=False),sa.Column('status',sa.String(20),nullable=False),
        sa.Column('starts_at',sa.DateTime(timezone=True),nullable=False),sa.Column('ends_at',sa.DateTime(timezone=True)),
        sa.Column('enforcement_enabled',sa.Boolean,nullable=False),sa.Column('external_customer_id',sa.String(255)),sa.Column('external_subscription_id',sa.String(255),unique=True),
        sa.CheckConstraint("status IN ('active','trialing','paused','expired','canceled')",name='ck_subscription_status'),
        sa.CheckConstraint('ends_at IS NULL OR ends_at > starts_at',name='ck_subscription_dates'))
    if op.get_bind().dialect.name=='postgresql':
        for table in ('subscription_plans','subscriptions'):
            op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY');op.execute(f'REVOKE ALL ON {table} FROM PUBLIC')
            for role in ('anon','authenticated'):
                op.execute(f"DO $safe$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN REVOKE ALL ON {table} FROM {role}; END IF; END $safe$")

def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM subscriptions) OR EXISTS(SELECT 1 FROM subscription_plans)')):
        raise RuntimeError('Refusing to discard configured subscription data')
    op.drop_table('subscriptions');op.drop_table('subscription_plans')
