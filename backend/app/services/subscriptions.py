from fastapi import HTTPException
from sqlalchemy import select,func
from app.core.sessions import utcnow,aware
from app.models import Organization,Membership
from app.models.invitation import OrganizationInvitation
from app.models.subscription import SubscriptionPlan,Subscription

FEATURES=('analytics','exports','workflows','attachments')
PILOT_CODE='free_pilot'
PILOT_EXPIRED='Free Pilot access expired or inactive. Contact platform administration for manual renewal.'


def pilot_definition():
    # Explicit operator configuration only; never seed this at startup/migration.
    return dict(name='Free Pilot',currency='USD',price=0,billing_interval='month',
                entitlements={f:True for f in FEATURES},seat_limit=5,published=True,external_price_id=None)


def require_pilot_access(db,org):
    # Core metadata read avoids recursive tenant-session hooks and stale ORM caches.
    s=Subscription.__table__.c;p=SubscriptionPlan.__table__.c
    row=db.connection().execute(select(s.status,s.starts_at,s.ends_at,s.enforcement_enabled)
        .select_from(Subscription.__table__.join(SubscriptionPlan.__table__,s.plan_id==p.id))
        .where(s.organization_id==org,p.code==PILOT_CODE)).first()
    if row and (not row.enforcement_enabled or not row.ends_at or row.status not in {'active','trialing'}
                or aware(row.starts_at)>utcnow() or aware(row.ends_at)<=utcnow()):
        raise HTTPException(403,PILOT_EXPIRED)

def current(db,org):
    return db.scalar(select(Subscription).where(Subscription.organization_id==org).execution_options(populate_existing=True))

def live(sub):
    return sub.status in {'active','trialing'} and aware(sub.starts_at)<=utcnow() and (sub.ends_at is None or aware(sub.ends_at)>utcnow())

def usage(db,org,exclude_invitation=None):
    # Bounded aggregate shared by tenant queries and platform metadata management.
    # Never expose identities or private CRM records; an explicit org is mandatory.
    members=Membership.__table__.c;invitations=OrganizationInvitation.__table__.c
    active=db.connection().scalar(select(func.count()).select_from(Membership.__table__).where(members.organization_id==org,members.is_active.is_(True),members.removed_at.is_(None)))
    stmt=select(func.count()).select_from(OrganizationInvitation.__table__).where(invitations.organization_id==org,invitations.status=='pending',invitations.expires_at>utcnow())
    if exclude_invitation is not None:stmt=stmt.where(invitations.id!=exclude_invitation)
    return active,db.connection().scalar(stmt)

def check_seat(db,org,exclude_invitation=None):
    # All admission paths and plan/subscription edits use this same organization lock.
    db.scalar(select(Organization).where(Organization.id==org).with_for_update())
    sub=current(db,org)
    if not sub or not sub.enforcement_enabled:return
    if not live(sub):raise HTTPException(403,'Subscription does not permit additional seats')
    plan=db.get(SubscriptionPlan,sub.plan_id,populate_existing=True)
    active,pending=usage(db,org,exclude_invitation)
    from app.services.usage import seat_limit
    limit=seat_limit(sub,plan)
    if limit is not None and active+pending>=limit:
        raise HTTPException(409,'Organization seat limit reached (including pending invitations)')

def feature_allowed(db,org,feature):
    sub=current(db,org)
    if not sub or not sub.enforcement_enabled:return True
    plan=db.get(SubscriptionPlan,sub.plan_id,populate_existing=True)
    return live(sub) and plan.entitlements.get(feature,False)

def require_feature(db,org,feature):
    if not feature_allowed(db,org,feature):raise HTTPException(403,'This subscription does not include '+feature)

def request_feature(db,org,path):
    path=path.removeprefix('/api/v1/')
    head=path.split('/')[0]
    feature={'dashboard':'analytics','analytics':'analytics','reports':'analytics','exports':'exports','workflows':'workflows','automations':'workflows','attachments':'attachments'}.get(head)
    if head=='records' and path.endswith('/attachments'):feature='attachments'
    if feature:require_feature(db,org,feature)

def plan_data(plan):
    return {k:getattr(plan,k) for k in ('id','code','name','currency','price','billing_interval','entitlements','seat_limit','published')}

def validate_capacity(db,org,limit):
    active,pending=usage(db,org)
    if limit is not None and active+pending>limit:raise HTTPException(409,'Seat limit is below current memberships and pending invitations')
