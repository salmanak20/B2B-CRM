from typing import Literal
from uuid import UUID
import re
import secrets
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, insert, update, func, or_
from app.api.deps import SessionDep, CurrentActiveUser
from app.api.routes.platform import Admin
from app.models import Organization, Membership, User
from app.models.onboarding import OrganizationProvision
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.usage import ResourceTotal, ResourceDay
from app.services.platform import authorize, lock_administration, verify_target, audit
from app.services.usage import insights, consumption, RESOURCES, PILOT_LIMITS

router = APIRouter(tags=['Usage and limits'])


class Quotas(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    limits: dict[str, int] = Field(min_length=8, max_length=8)
    expected_limits: dict[str, int] | None
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode='before')
    @classmethod
    def valid_limits(cls, values):
        limits = values.get('limits', {})
        if set(limits) != set(PILOT_LIMITS) or any(type(v) is not int or v < (1 if k == 'seats' else 0) or v > 9007199254740991 for k,v in limits.items()):
            raise ValueError('Specify every resource with a finite nonnegative integer limit and at least one seat')
        return values


@router.get('/subscription/usage')
def own_usage(db:SessionDep, user:CurrentActiveUser, days:int=Query(30, ge=1, le=366), interval:Literal['day','week','month']='day'):
    return insights(db, user.organization_id, days, interval)


@router.get('/platform/organizations/{org_id}/usage')
def business_usage(org_id:int, db:SessionDep, admin:Admin, days:int=Query(30, ge=1, le=366), interval:Literal['day','week','month']='day'):
    if not db.get(Organization, org_id): raise HTTPException(404, 'Business not found')
    return insights(db, org_id, days, interval)


@router.get('/platform/organizations/{org_id}/limits')
def limits(org_id:int, db:SessionDep, admin:Admin):
    sub=db.scalar(select(Subscription).where(Subscription.organization_id==org_id))
    if not sub: raise HTTPException(409, 'Approve a subscription before setting quotas')
    return dict(limits=sub.resource_limits, defaults_for_new_pilots=PILOT_LIMITS, consumption=consumption(db,org_id))


@router.put('/platform/organizations/{org_id}/limits')
def set_limits(org_id:int, body:Quotas, db:SessionDep, admin:Admin, request:Request):
    lock_administration(db); authorize(db,request,admin)
    if not db.scalar(select(Organization).where(Organization.id==org_id).with_for_update()):
        raise HTTPException(404,'Business not found')
    sub=db.scalar(select(Subscription).where(Subscription.organization_id==org_id).execution_options(populate_existing=True))
    if not sub or not sub.enforcement_enabled: raise HTTPException(409,'An enforced subscription is required')
    if sub.resource_limits != body.expected_limits: raise HTTPException(409,'Limits changed; reload before saving')
    previous=sub.resource_limits
    sub.resource_limits=dict(body.limits)
    # Values are operational metadata; no CRM contents appear in platform audit.
    audit(db,admin.id,'quotas_changed',org_id,f'{body.reason}; previous={previous}; limits={body.limits}')
    db.commit()
    return dict(limits=sub.resource_limits,consumption=consumption(db,org_id))


@router.get('/platform/usage-summary')
def aggregate_usage(db:SessionDep, admin:Admin):
    conn=db.connection()
    totals=dict(conn.execute(select(ResourceTotal.resource,func.sum(ResourceTotal.total)).group_by(ResourceTotal.resource)).all())
    m=Membership.__table__
    u=User.__table__
    owner_count=conn.scalar(select(func.count(func.distinct(m.c.user_id))).select_from(m.join(u,m.c.user_id==u.c.id)).where(m.c.role=='owner',m.c.is_active.is_(True),m.c.removed_at.is_(None),u.c.is_active.is_(True)))
    employees=conn.scalar(select(func.count()).select_from(m.join(u,m.c.user_id==u.c.id)).where(m.c.role!='owner',m.c.is_active.is_(True),m.c.removed_at.is_(None),u.c.is_active.is_(True)))
    from app.models.invitation import OrganizationInvitation
    from app.core.sessions import utcnow
    active=select(m.c.organization_id,func.count().label('used')).where(m.c.is_active.is_(True),m.c.removed_at.is_(None)).group_by(m.c.organization_id).subquery()
    i=OrganizationInvitation.__table__
    pending=select(i.c.organization_id,func.count().label('used')).where(i.c.status=='pending',i.c.expires_at>utcnow()).group_by(i.c.organization_id).subquery()
    allowance=func.coalesce(Subscription.resource_limits['seats'].as_integer(),SubscriptionPlan.seat_limit)
    near_seats=conn.scalar(select(func.count()).select_from(Subscription).join(SubscriptionPlan).outerjoin(active,active.c.organization_id==Subscription.organization_id).outerjoin(pending,pending.c.organization_id==Subscription.organization_id).where(Subscription.enforcement_enabled.is_(True),allowance.is_not(None),func.coalesce(active.c.used,0)+func.coalesce(pending.c.used,0)>=allowance*0.8))
    quota=Subscription.resource_limits[ResourceTotal.resource].as_integer()
    near_resources=db.scalar(select(func.count(func.distinct(ResourceTotal.organization_id))).join(Subscription,Subscription.organization_id==ResourceTotal.organization_id).where(Subscription.enforcement_enabled.is_(True),quota.is_not(None),ResourceTotal.total>=quota*0.8))
    expired_pilots=db.scalar(select(func.count()).select_from(Subscription).join(SubscriptionPlan).where(SubscriptionPlan.code=='free_pilot',or_(Subscription.ends_at<=utcnow(),Subscription.status.in_(['expired','canceled','paused']))))
    return dict(current_totals=totals,owners=owner_count,active_employee_seats=employees,near_seat_limits=near_seats,near_resource_limits=near_resources,expired_pilots=expired_pilots,
        history_note='Resource totals are current allocation, not historical creation counts.')


class ResourceRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    reason:str=Field(min_length=1,max_length=300)


@router.post('/subscription/resource-request')
def request_resources(body:ResourceRequest, db:SessionDep, user:CurrentActiveUser, request:Request):
    if user.organization_role not in {'owner','admin'}: raise HTTPException(403,'Owner or administrator access required')
    from app.core.rate_limit import limit_auth
    # Reuse persistent request throttling; no email delivery is implied.
    limit_auth(db,request,user.email,'resource-request')
    audit(db,user.id,'resources_requested',user.organization_id,body.reason)
    db.commit()
    return {'message':'Request recorded for platform administration review.'}


class RegisterBusiness(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=100)
    owner_id:int=Field(gt=0)
    request_key:UUID
    reason:str=Field(min_length=1,max_length=300)


@router.post('/platform/organizations')
def register_business(body:RegisterBusiness, db:SessionDep, admin:Admin, request:Request):
    lock_administration(db); authorize(db,request,admin)
    owner=verify_target(db,body.owner_id)
    receipt=db.scalar(select(OrganizationProvision).where(OrganizationProvision.user_id==owner.id,OrganizationProvision.request_key==str(body.request_key)))
    if receipt:
        if receipt.name!=body.name: raise HTTPException(409,'Request key already used for different details')
        return {'organization_id':receipt.organization_id,'awaiting_approval':True}
    slug=re.sub(r'[^a-z0-9]+','-',body.name.lower()).strip('-')[:70] or 'business'
    org=Organization(name=body.name,slug=slug+'-'+secrets.token_hex(6),is_suspended=True)
    db.add(org);db.flush()
    # Platform metadata operation only; no tenant-session bypass or Auth creation.
    db.connection().execute(insert(Membership.__table__).values(organization_id=org.id,user_id=owner.id,role='owner',permission_role_name='admin',is_active=True))
    db.add(OrganizationProvision(user_id=owner.id,request_key=str(body.request_key),name=body.name,organization_id=org.id))
    audit(db,admin.id,'business_registered',org.id,f'Approved existing owner {owner.id}; {body.reason}')
    db.commit()
    return {'organization_id':org.id,'awaiting_approval':True}


class AssignOwner(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    user_id:int=Field(gt=0)
    reason:str=Field(min_length=1,max_length=300)


@router.put('/platform/organizations/{org_id}/owner')
def assign_owner(org_id:int, body:AssignOwner, db:SessionDep, admin:Admin, request:Request):
    lock_administration(db); authorize(db,request,admin)
    if not db.scalar(select(Organization).where(Organization.id==org_id).with_for_update()): raise HTTPException(404,'Business not found')
    target=verify_target(db,body.user_id)
    table=Membership.__table__
    member=db.connection().execute(select(table).where(table.c.organization_id==org_id,table.c.user_id==target.id)).mappings().first()
    if not member or not member['is_active'] or member['removed_at']:
        from app.services.subscriptions import check_seat
        check_seat(db,org_id)
    values=dict(role='owner',permission_role_name='admin',is_active=True,removed_at=None)
    if member: db.connection().execute(update(table).where(table.c.id==member['id']).values(**values))
    else: db.connection().execute(insert(table).values(organization_id=org_id,user_id=target.id,**values))
    audit(db,admin.id,'owner_assigned',org_id,f'Explicit owner {target.id}; {body.reason}')
    db.commit();return {'ok':True}
