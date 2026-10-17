from fastapi import HTTPException
from sqlalchemy import select,func
from app.core.sessions import utcnow,aware
from app.models import Organization,Membership
from app.models.invitation import OrganizationInvitation
from app.models.subscription import SubscriptionPlan,Subscription

FEATURES=('analytics','exports','workflows','attachments')

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
    if plan.seat_limit is not None and active+pending>=plan.seat_limit:
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
