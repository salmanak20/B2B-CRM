"""Bounded aggregate reads. Access is authorized by the calling route."""
from datetime import timedelta
from sqlalchemy import select, func
from app.core.sessions import utcnow
from app.models.usage import ResourceTotal, ResourceDay, WorkflowPeriod, UsageInstrumentation
from app.models.subscription import Subscription, SubscriptionPlan
from app.services.subscriptions import current, usage

RESOURCES = ('leads', 'contacts', 'companies', 'deals', 'tasks', 'storage_bytes', 'workflow_executions')
PILOT_LIMITS = dict(seats=5, leads=500, contacts=500, companies=250, deals=500,
                    tasks=1000, storage_bytes=1073741824, workflow_executions=1000)


def seat_limit(sub, plan):
    return (sub.resource_limits or {}).get('seats', plan.seat_limit)


def consumption(db, org):
    totals = dict(db.connection().execute(select(ResourceTotal.resource, ResourceTotal.total)
        .where(ResourceTotal.organization_id == org)).all())
    sub = current(db, org)
    plan = db.get(SubscriptionPlan, sub.plan_id) if sub else None
    limits = sub.resource_limits if sub and sub.enforcement_enabled else None
    active, pending = usage(db, org)
    executions = 0
    if sub:
        executions = db.connection().scalar(select(WorkflowPeriod.executions).where(
            WorkflowPeriod.organization_id == org, WorkflowPeriod.starts_at == sub.starts_at)) or 0
    values = {r: totals.get(r, 0) for r in RESOURCES}
    values.update(seats=active + pending, workflow_executions=executions)
    result = {}
    for resource, value in values.items():
        limit = seat_limit(sub, plan) if resource == 'seats' and sub and sub.enforcement_enabled else (limits or {}).get(resource)
        result[resource] = dict(used=value, limit=limit, remaining=max(0, limit-value) if limit is not None else None,
            percent=round(value*100/limit, 1) if limit else (100 if limit == 0 and value else 0 if limit == 0 else None))
    return result


def insights(db, org, days=30, interval='day'):
    first = utcnow().date() - timedelta(days=days-1)
    t = ResourceDay.__table__
    # A maximum of 366 days times 9 resources; never read private CRM tables.
    rows = db.connection().execute(select(t).where(t.c.organization_id == org, t.c.day >= first)
        .order_by(t.c.day).limit(366*10)).mappings().all()
    buckets = {}
    for row in rows:
        day = row['day']
        bucket = day - timedelta(days=day.weekday()) if interval == 'week' else day.replace(day=1) if interval == 'month' else day
        key = (bucket, row['resource'])
        target = buckets.setdefault(key, dict(period=bucket, resource=row['resource'], created=0, deleted=0, updated=0, added_units=0, removed_units=0))
        for field in ('created', 'deleted', 'updated', 'added_units', 'removed_units'):
            target[field] += row[field]
    started = db.connection().scalar(select(UsageInstrumentation.started_at).limit(1))
    last = db.connection().scalar(select(func.max(ResourceDay.last_activity)).where(ResourceDay.organization_id == org))
    return dict(organization_id=org, days=days, interval=interval, history_started_at=started,
        history_note='Only writes recorded after instrumentation are shown. Current totals include existing records. Attachment bytes include pending reservations. Workflow executions count this access period since instrumentation. API request counts are unavailable.',
        api_requests=None, last_recorded_activity=last, resources=consumption(db, org),
        trends=list(buckets.values()))
