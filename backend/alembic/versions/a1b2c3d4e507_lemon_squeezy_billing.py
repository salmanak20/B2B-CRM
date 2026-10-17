"""Test billing bindings only; existing subscriptions and access are unchanged."""
from alembic import op
import sqlalchemy as sa
revision='a1b2c3d4e507'
down_revision='a1b2c3d4e506'
branch_labels=None
depends_on=None

def upgrade():
    for name,kind in [('provider_status',sa.String(30)),('provider_updated_at',sa.DateTime(timezone=True)),('provider_order_id',sa.String(30)),('past_due_since',sa.DateTime(timezone=True))]:
        op.add_column('subscriptions',sa.Column(name,kind,nullable=True))
    op.create_index('ix_subscriptions_provider_order_id','subscriptions',['provider_order_id'])
    op.create_table('billing_checkouts',sa.Column('token',sa.String(64),primary_key=True),
        sa.Column('organization_id',sa.Integer,sa.ForeignKey('organizations.id'),nullable=False),sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('plan_id',sa.Integer,sa.ForeignKey('subscription_plans.id'),nullable=False),sa.Column('request_key',sa.String(36),nullable=False),
        sa.Column('product_id',sa.String(30),nullable=False),sa.Column('variant_id',sa.String(30),nullable=False),
        sa.Column('provider_checkout_id',sa.String(100),unique=True),sa.Column('checkout_url',sa.String(2000)),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('state',sa.String(20),nullable=False),
        sa.UniqueConstraint('organization_id','request_key',name='uq_billing_checkout_request'))
    op.create_index('ix_billing_checkouts_organization_id','billing_checkouts',['organization_id'])
    op.create_table('billing_events',sa.Column('digest',sa.String(64),primary_key=True),sa.Column('event_name',sa.String(80),nullable=False),sa.Column('resource_id',sa.String(100),nullable=False),sa.Column('received_at',sa.DateTime(timezone=True),nullable=False))
    if op.get_bind().dialect.name=='postgresql':
        for table in ('billing_checkouts','billing_events'):
            op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY');op.execute(f'REVOKE ALL ON {table} FROM PUBLIC')
            for role in ('anon','authenticated'):
                op.execute(f"DO $safe$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN REVOKE ALL ON {table} FROM {role}; END IF; END $safe$")

def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM billing_checkouts) OR EXISTS(SELECT 1 FROM billing_events) OR EXISTS(SELECT 1 FROM subscriptions WHERE provider_status IS NOT NULL)')):
        raise RuntimeError('Refusing to discard billing state')
    op.drop_table('billing_events');op.drop_table('billing_checkouts')
    op.drop_index('ix_subscriptions_provider_order_id',table_name='subscriptions')
    for name in ('past_due_since','provider_order_id','provider_updated_at','provider_status'):op.drop_column('subscriptions',name)
