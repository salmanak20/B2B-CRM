from decimal import Decimal
from datetime import timedelta
from typing import Literal
from fastapi import APIRouter,Request,HTTPException
from pydantic import BaseModel,ConfigDict,Field,AwareDatetime,StrictBool,model_validator
from sqlalchemy import select
from app.api.deps import SessionDep,CurrentActiveUser
from app.api.routes.platform import Admin
from app.services.platform import authorize,lock_administration,audit,verify_target
from app.services.subscriptions import current,usage,plan_data,validate_capacity,FEATURES,live,PILOT_CODE,pilot_definition
from app.core.sessions import utcnow,aware
from app.models import Organization,Membership
from app.models.subscription import SubscriptionPlan,Subscription

router=APIRouter(tags=['Subscriptions'])

class PlanInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=100)
    currency:str=Field(pattern='^[A-Z]{3}$')
    price:Decimal|None=Field(None,ge=0,max_digits=14,decimal_places=2)
    billing_interval:Literal['month','year']
    entitlements:dict[str,StrictBool]=Field(default_factory=dict)
    seat_limit:int|None=Field(None,ge=1,strict=True)
    published:bool=False
    external_price_id:str|None=Field(None,max_length=255)
    reason:str=Field(min_length=1,max_length=500)
    @model_validator(mode='after')
    def known_features(self):
        if set(self.entitlements)-set(FEATURES):raise ValueError('Unknown feature entitlement')
        return self

class SubscriptionInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    plan_id:int=Field(gt=0)
    status:Literal['active','trialing','paused','expired','canceled']
    starts_at:AwareDatetime=Field(default_factory=utcnow)
    ends_at:AwareDatetime|None=None
    enforcement_enabled:StrictBool=False
    external_customer_id:str|None=Field(None,max_length=255)
    external_subscription_id:str|None=Field(None,max_length=255)
    reason:str=Field(min_length=1,max_length=500)
    pilot_action:Literal['activate','extend']|None=None
    approved_owner_id:int|None=Field(None,gt=0)
    expected_ends_at:AwareDatetime|None=None
    @model_validator(mode='after')
    def dates(self):
        if self.ends_at and self.ends_at<=self.starts_at:raise ValueError('End must follow start')
        return self

def summary(db,org):
    from app.services.usage import seat_limit
    sub=current(db,org);active,pending=usage(db,org)
    plan=db.get(SubscriptionPlan,sub.plan_id) if sub else None
    enforced=bool(sub and sub.enforcement_enabled)
    from app.services.lemon_squeezy import available
    return {'access_status':('active' if live(sub) else 'expired_or_inactive') if sub and plan.code==PILOT_CODE else None,'can_manage_billing':False,'provider_status':sub.provider_status if sub else None,'test_billing_available':available(),'plan':plan_data(plan) if plan else None,'subscription':{k:getattr(sub,k) for k in ('status','starts_at','ends_at','enforcement_enabled')} if sub else None,
        'seats':{'active':active,'pending':pending,'limit':seat_limit(sub,plan) if enforced else None},
        'entitlements':{f:(not enforced or (live(sub) and plan.entitlements.get(f,False))) for f in FEATURES},'billing_available':False}

@router.get('/subscription/plans')
def plans(db:SessionDep,user:CurrentActiveUser):
    return [plan_data(p) for p in db.scalars(select(SubscriptionPlan).where(SubscriptionPlan.published.is_(True)).order_by(SubscriptionPlan.id))]

@router.get('/subscription')
def subscription(db:SessionDep,user:CurrentActiveUser):
    result=summary(db,user.organization_id);result['can_manage_billing']=user.organization_role=='owner';return result

@router.get('/platform/plans')
def platform_plans(db:SessionDep,admin:Admin):return [plan_data(p) for p in db.scalars(select(SubscriptionPlan).order_by(SubscriptionPlan.id))]

@router.put('/platform/plans/{code}')
def configure_plan(code:Literal['starter','business','enterprise','free_pilot'],body:PlanInput,db:SessionDep,admin:Admin,request:Request):
    lock_administration(db);authorize(db,request,admin)
    if code==PILOT_CODE and body.model_dump(exclude={'reason'})!=pilot_definition():
        raise HTTPException(422,'Free Pilot requires the approved fixed five-seat feature configuration')
    plan=db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code==code))
    if plan:
        orgs=list(db.scalars(select(Subscription.organization_id).where(Subscription.plan_id==plan.id,Subscription.enforcement_enabled.is_(True)).order_by(Subscription.organization_id)))
        for org in orgs:
            db.scalar(select(Organization).where(Organization.id==org).with_for_update())
            subscription=current(db,org)
            validate_capacity(db,org,(subscription.resource_limits or {}).get('seats',body.seat_limit))
    else:
        plan=SubscriptionPlan(code=code);db.add(plan)
    values=body.model_dump(exclude={'reason'})
    if code==PILOT_CODE and plan.id and all(getattr(plan,k)==v for k,v in values.items()):
        return plan_data(plan)
    for key,value in values.items():setattr(plan,key,value)
    db.flush();audit(db,admin.id,'plan_configured',plan.id,body.reason);db.commit();return plan_data(plan)

@router.get('/platform/subscriptions/{org_id}')
def platform_subscription(org_id:int,db:SessionDep,admin:Admin):
    if not db.get(Organization,org_id):raise HTTPException(404,'Organization not found')
    return summary(db,org_id)

@router.put('/platform/subscriptions/{org_id}')
def configure_subscription(org_id:int,body:SubscriptionInput,db:SessionDep,admin:Admin,request:Request):
    lock_administration(db);authorize(db,request,admin)
    org=db.scalar(select(Organization).where(Organization.id==org_id).with_for_update())
    if not org:raise HTTPException(404,'Organization not found')
    plan=db.get(SubscriptionPlan,body.plan_id)
    if not plan:raise HTTPException(422,'Plan not found')
    sub=current(db,org_id)
    if plan.code==PILOT_CODE:
        return configure_pilot(db,admin,org,plan,sub,body)
    if body.pilot_action or body.approved_owner_id or body.expected_ends_at:
        raise HTTPException(422,'Pilot approval fields require the Free Pilot plan')
    if sub and db.get(SubscriptionPlan,sub.plan_id).code==PILOT_CODE:
        raise HTTPException(409,'Use explicit Free Pilot renewal; changing its access policy requires separate configuration')
    if body.enforcement_enabled:validate_capacity(db,org_id,plan.seat_limit)
    if not sub:sub=Subscription(organization_id=org_id);db.add(sub)
    if sub.provider_status is not None:raise HTTPException(409,'Provider-managed subscriptions must be reconciled from verified provider state')
    for key,value in body.model_dump(exclude={'reason','pilot_action','approved_owner_id','expected_ends_at'}).items():setattr(sub,key,value)
    db.flush();audit(db,admin.id,'subscription_configured',org_id,body.reason);db.commit()
    return summary(db,org_id)


def configure_pilot(db,admin,org,plan,sub,body):
    if (not body.pilot_action or not body.approved_owner_id or body.status!='active' or not body.enforcement_enabled
        or body.external_customer_id or body.external_subscription_id
        or {'starts_at','ends_at'} & body.model_fields_set):
        raise HTTPException(422,'Explicit owner approval and enforced active Free Pilot required; dates are server controlled')
    if any(getattr(plan,k)!=v for k,v in pilot_definition().items()):
        raise HTTPException(409,'Free Pilot configuration requires review')
    owner=db.scalar(select(Membership).where(Membership.organization_id==org.id,
        Membership.user_id==body.approved_owner_id,Membership.role=='owner',Membership.is_active.is_(True),Membership.removed_at.is_(None)))
    if not owner:raise HTTPException(422,'Approve an existing active organization owner; no ownership is created')
    verify_target(db,body.approved_owner_id)
    from app.services.usage import seat_limit, PILOT_LIMITS
    validate_capacity(db,org.id,seat_limit(sub,plan) if sub else 5)
    if sub and (sub.plan_id!=plan.id or sub.provider_status is not None or sub.external_subscription_id):
        raise HTTPException(409,'Existing customer subscription cannot be replaced by a Pilot')
    if body.pilot_action=='activate' and sub:
        if not live(sub):raise HTTPException(409,'Pilot expired or inactive; explicit renewal is required')
        return summary(db,org.id)  # Retry never moves the original approval dates.
    if body.pilot_action=='extend':
        if not sub or not body.expected_ends_at or not sub.ends_at or aware(body.expected_ends_at)!=aware(sub.ends_at):
            raise HTTPException(409,'Pilot changed; reload before explicitly renewing')
    elif body.expected_ends_at:
        raise HTTPException(422,'Initial activation does not take a previous expiry')
    if not sub:sub=Subscription(organization_id=org.id,resource_limits=dict(PILOT_LIMITS));db.add(sub)
    now=utcnow()
    sub.plan_id=plan.id;sub.status='active';sub.enforcement_enabled=True
    sub.starts_at=now;sub.ends_at=now+timedelta(days=30)
    db.flush();audit(db,admin.id,'pilot_'+body.pilot_action,org.id,body.reason);db.commit()
    return summary(db,org.id)
