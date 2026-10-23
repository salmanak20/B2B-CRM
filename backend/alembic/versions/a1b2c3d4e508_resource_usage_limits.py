"""Private aggregate instrumentation and explicit per-business resource limits."""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e508'
down_revision = 'a1b2c3d4e507'
branch_labels = depends_on = None

TABLES = ('leads', 'contacts', 'companies', 'deals', 'tasks', 'attachments', 'workflow_runs', 'activities', 'audit_logs')


def upgrade():
    op.alter_column('organization_invitations','provider_user_id',existing_type=sa.String(36),nullable=True)
    op.add_column('subscriptions', sa.Column('resource_limits', sa.JSON, nullable=True))
    op.create_table('resource_totals',
        sa.Column('organization_id', sa.Integer, sa.ForeignKey('organizations.id'), primary_key=True),
        sa.Column('resource', sa.String(30), primary_key=True), sa.Column('total', sa.BigInteger, nullable=False, server_default='0'))
    op.create_table('resource_days',
        sa.Column('organization_id', sa.Integer, sa.ForeignKey('organizations.id'), primary_key=True),
        sa.Column('day', sa.Date, primary_key=True), sa.Column('resource', sa.String(30), primary_key=True),
        *[sa.Column(n, sa.BigInteger, nullable=False, server_default='0') for n in ('created','deleted','updated','added_units','removed_units')],
        sa.Column('last_activity', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table('workflow_periods',
        sa.Column('organization_id', sa.Integer, sa.ForeignKey('organizations.id'), primary_key=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), primary_key=True),
        sa.Column('executions', sa.BigInteger, nullable=False, server_default='0'))
    op.create_table('usage_instrumentation', sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.execute('INSERT INTO usage_instrumentation(id) VALUES (1)')
    # Exact current totals only. No invented historic activity or execution dates.
    for table in TABLES:
        units = 'SUM(size)' if table == 'attachments' else 'COUNT(*)'
        resource = 'storage_bytes' if table == 'attachments' else table
        op.execute(f"INSERT INTO resource_totals(organization_id,resource,total) SELECT organization_id,'{resource}',{units} FROM {table} WHERE organization_id IS NOT NULL GROUP BY organization_id")
    if op.get_bind().dialect.name != 'postgresql':
        return
    for table in ('resource_totals','resource_days','workflow_periods','usage_instrumentation'):
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON {table} FROM PUBLIC')
        for role in ('anon','authenticated'):
            op.execute(f"DO $safe$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN REVOKE ALL ON {table} FROM {role}; END IF; END $safe$")
    op.execute("""CREATE FUNCTION crm_record_usage() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE org integer; previous_org integer; resource_name text; delta bigint; amount bigint;
        current_total bigint; max_allowed bigint; limits json; enforced boolean;
        period_start timestamptz; period_used bigint; plan_code text;
BEGIN
    IF TG_OP='DELETE' THEN org=OLD.organization_id; ELSE org=NEW.organization_id; END IF;
    resource_name=CASE WHEN TG_TABLE_NAME='attachments' THEN 'storage_bytes' ELSE TG_TABLE_NAME END;
    IF TG_OP='UPDATE' AND OLD.organization_id IS DISTINCT FROM NEW.organization_id THEN
        -- Explicit legacy linkage updates current totals only, never historic events.
        IF OLD.organization_id IS NOT NULL THEN
            RAISE EXCEPTION 'CRM_ORGANIZATION_IMMUTABLE' USING ERRCODE='23514';
        END IF;
        IF org IS NOT NULL THEN
            PERFORM 1 FROM public.organizations WHERE id=org FOR NO KEY UPDATE;
            amount=CASE WHEN TG_TABLE_NAME='attachments' THEN (to_jsonb(NEW)->>'size')::bigint ELSE 1 END;
            INSERT INTO public.resource_totals VALUES(org,resource_name,amount)
            ON CONFLICT(organization_id,resource) DO UPDATE SET total=resource_totals.total+EXCLUDED.total;
        END IF;
        RETURN NEW;
    END IF;
    IF org IS NULL THEN RETURN COALESCE(NEW,OLD); END IF;
    -- Shared with seat admission, quota edits, and subscription renewal.
    PERFORM 1 FROM public.organizations WHERE id=org FOR NO KEY UPDATE;
    amount=CASE WHEN TG_TABLE_NAME='attachments' THEN COALESCE((to_jsonb(NEW)->>'size')::bigint,(to_jsonb(OLD)->>'size')::bigint) ELSE 1 END;
    delta=CASE WHEN TG_OP='INSERT' THEN amount WHEN TG_OP='DELETE' THEN -amount
        WHEN TG_TABLE_NAME='attachments' THEN (to_jsonb(NEW)->>'size')::bigint-(to_jsonb(OLD)->>'size')::bigint ELSE 0 END;
    INSERT INTO public.resource_totals VALUES(org,resource_name,0) ON CONFLICT DO NOTHING;
    SELECT total INTO current_total FROM public.resource_totals WHERE organization_id=org AND resource=resource_name;
    SELECT s.resource_limits,s.enforcement_enabled,s.starts_at,p.code INTO limits,enforced,period_start,plan_code
        FROM public.subscriptions s JOIN public.subscription_plans p ON p.id=s.plan_id WHERE s.organization_id=org;
    IF TG_TABLE_NAME='workflow_runs' AND TG_OP='INSERT' AND period_start IS NOT NULL THEN
        INSERT INTO public.workflow_periods VALUES(org,period_start,0) ON CONFLICT DO NOTHING;
        SELECT executions INTO period_used FROM public.workflow_periods WHERE organization_id=org AND starts_at=period_start;
        max_allowed=(limits->>'workflow_executions')::bigint;
        IF enforced AND (max_allowed IS NOT NULL AND period_used+1>max_allowed OR plan_code='free_pilot' AND max_allowed IS NULL) THEN
            RAISE EXCEPTION 'CRM_QUOTA:workflow_executions' USING ERRCODE='23514';
        END IF;
        UPDATE public.workflow_periods SET executions=executions+1 WHERE organization_id=org AND starts_at=period_start;
    END IF;
    IF resource_name IN ('leads','contacts','companies','deals','tasks','storage_bytes') AND delta>0 AND enforced THEN
        max_allowed=(limits->>resource_name)::bigint;
        IF max_allowed IS NOT NULL AND current_total+delta>max_allowed OR plan_code='free_pilot' AND max_allowed IS NULL THEN
            RAISE EXCEPTION 'CRM_QUOTA:%',resource_name USING ERRCODE='23514';
        END IF;
    END IF;
    UPDATE public.resource_totals SET total=total+delta WHERE organization_id=org AND resource=resource_name;
    INSERT INTO public.resource_days(organization_id,day,resource,created,deleted,updated,added_units,removed_units,last_activity)
        VALUES(org,(clock_timestamp() AT TIME ZONE 'UTC')::date,resource_name,
            CASE WHEN TG_OP='INSERT' THEN 1 ELSE 0 END, CASE WHEN TG_OP='DELETE' THEN 1 ELSE 0 END,
            CASE WHEN TG_OP='UPDATE' THEN 1 ELSE 0 END,GREATEST(delta,0),GREATEST(-delta,0),clock_timestamp())
        ON CONFLICT(organization_id,day,resource) DO UPDATE SET
            created=resource_days.created+EXCLUDED.created,deleted=resource_days.deleted+EXCLUDED.deleted,
            updated=resource_days.updated+EXCLUDED.updated,added_units=resource_days.added_units+EXCLUDED.added_units,
            removed_units=resource_days.removed_units+EXCLUDED.removed_units,last_activity=EXCLUDED.last_activity;
    RETURN COALESCE(NEW,OLD);
END $$;
REVOKE ALL ON FUNCTION crm_record_usage() FROM PUBLIC;
""")
    for table in TABLES:
        op.execute(f'CREATE TRIGGER crm_usage AFTER INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION crm_record_usage()')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM organization_invitations WHERE provider_user_id IS NULL)')):
        raise RuntimeError('Refusing to discard pending undelivered invitations')
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM resource_days) OR EXISTS(SELECT 1 FROM subscriptions WHERE resource_limits IS NOT NULL)')):
        raise RuntimeError('Refusing to discard quota configuration or recorded usage')
    if op.get_bind().dialect.name == 'postgresql':
        for table in TABLES:
            op.execute(f'DROP TRIGGER crm_usage ON {table}')
        op.execute('DROP FUNCTION crm_record_usage()')
    for table in ('usage_instrumentation','workflow_periods','resource_days','resource_totals'):
        op.drop_table(table)
    op.drop_column('subscriptions','resource_limits')
    op.alter_column('organization_invitations','provider_user_id',existing_type=sa.String(36),nullable=False)
