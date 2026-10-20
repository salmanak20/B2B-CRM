from typing import Annotated,Literal
from fastapi import APIRouter,Depends,Request,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,func,delete,update,case,and_,or_
from datetime import timedelta
from app.api.deps import SessionDep,CurrentUser
from app.models import Organization,Membership,User
from app.models.platform import PlatformAdministrator,PlatformAudit
from app.models.session import AuthSession
from app.services.platform import authorize,verify_target,lock_administration,audit
from app.core.sessions import utcnow
from app.models.subscription import Subscription,SubscriptionPlan
from app.models.invitation import OrganizationInvitation


def inventory():
    """Only organization/access metadata. Never join customer CRM tables."""
    now=utcnow()
    live=and_(Subscription.status.in_(['active','trialing']),Subscription.starts_at<=now,
        or_(Subscription.ends_at.is_(None),Subscription.ends_at>now),
        or_(SubscriptionPlan.code!='free_pilot',and_(Subscription.enforcement_enabled.is_(True),Subscription.ends_at.is_not(None))))
    state=case((Organization.is_suspended.is_(True),'suspended'),
        (Subscription.id.is_(None),'pending'),(live,'active'),else_='expired')
    return select(Organization,Subscription,SubscriptionPlan,state.label('access_status')).outerjoin(
        Subscription,Subscription.organization_id==Organization.id).outerjoin(SubscriptionPlan,SubscriptionPlan.id==Subscription.plan_id)


def business_row(db,row):
    from app.services.subscriptions import usage
    org,sub,plan,status=row
    active,pending=usage(db,org.id)
    return dict(id=org.id,name=org.name,slug=org.slug,is_suspended=org.is_suspended,
        created_at=org.created_at,access_status=status,members=active,pending_invitations=pending,
        seat_limit=plan.seat_limit if plan and sub.enforcement_enabled else None,
        plan=plan.name if plan else None,ends_at=sub.ends_at if sub else None)

router=APIRouter(prefix='/platform',tags=['platform'])
def platform_user(db:SessionDep,request:Request,user:CurrentUser):return authorize(db,request,user)
Admin=Annotated[User,Depends(platform_user)]

def org_summary(db,o):
    owners=db.execute(select(User.id,User.name,User.email,User.auth_user_id).join(Membership).where(
        Membership.organization_id==o.id,Membership.role=='owner',Membership.is_active.is_(True),Membership.removed_at.is_(None),User.is_active.is_(True))).all()
    # Auth links alone are not proof of confirmed email. Verify owners with the provider.
    verified=[]
    for owner in owners:
        if owner.auth_user_id:
            from app.services.platform import auth_request
            identity=auth_request('GET','/admin/users/'+owner.auth_user_id,admin=True)
            identity=identity.get('user',identity)
            if identity.get('id')==owner.auth_user_id and identity.get('email_confirmed_at') and str(identity.get('email','')).lower()==owner.email.lower():
                verified.append({'id':owner.id,'name':owner.name,'email':owner.email})
    return {'id':o.id,'name':o.name,'slug':o.slug,'is_suspended':o.is_suspended,'created_at':o.created_at,'verified_owners':verified}

@router.get('/summary')
def summary(db:SessionDep,admin:Admin):
    rows=inventory().subquery()
    counts=dict(db.execute(select(rows.c.access_status,func.count()).group_by(rows.c.access_status)).all())
    # Match subscription seat accounting; a retained active membership reserves
    # its seat even when the global account is inactive. Users are counted once.
    active_members=select(Membership).where(Membership.is_active.is_(True),Membership.removed_at.is_(None)).subquery()
    pilots=db.execute(select(Subscription.ends_at).join(SubscriptionPlan).join(Organization).where(
        SubscriptionPlan.code=='free_pilot',Subscription.status.in_(['active','trialing']),
        Subscription.enforcement_enabled.is_(True),Subscription.starts_at<=utcnow(),
        Subscription.ends_at>utcnow(),Organization.is_suspended.is_(False))).scalars().all()
    return dict(businesses=sum(counts.values()),active=counts.get('active',0),suspended=counts.get('suspended',0),
        expired=counts.get('expired',0),pending=counts.get('pending',0),
        memberships=db.scalar(select(func.count()).select_from(Membership)),
        occupied_seats=db.scalar(select(func.count()).select_from(active_members)),
        active_users=db.scalar(select(func.count(func.distinct(active_members.c.user_id))).join(User,User.id==active_members.c.user_id).where(User.is_active.is_(True))),
        active_pilots=len(pilots),expiring_pilots=sum(end<=utcnow()+timedelta(days=7) for end in pilots))

@router.get('/organizations')
def organizations(db:SessionDep,admin:Admin,q:str=Query('',max_length=100),status:Literal['all','active','suspended','expired','pending']='all',offset:int=Query(0,ge=0)):
    stmt=inventory().where(Organization.name.ilike('%'+q+'%'))
    if status!='all':stmt=stmt.where(stmt.selected_columns.access_status==status)
    return [business_row(db,r) for r in db.execute(stmt.order_by(Organization.id).offset(offset).limit(100))]

@router.get('/organizations/{org_id}')
def details(org_id:int,db:SessionDep,admin:Admin):
    org=db.get(Organization,org_id)
    if not org:raise HTTPException(404,'Business not found')
    return {**org_summary(db,org),**business_row(db,db.execute(inventory().where(Organization.id==org_id)).one())}


@router.get('/organizations/{org_id}/members')
def members(org_id:int,db:SessionDep,admin:Admin,offset:int=Query(0,ge=0)):
    if not db.get(Organization,org_id):raise HTTPException(404,'Business not found')
    return [dict(user_id=u.id,name=u.name,email=u.email,role=m.role,
        is_active=m.is_active and u.is_active and m.removed_at is None,auth_linked=bool(u.auth_user_id))
        for m,u in db.execute(select(Membership,User).join(User).where(Membership.organization_id==org_id).order_by(User.id).offset(offset).limit(100))]


@router.get('/organizations/{org_id}/members/{user_id}/identity')
def member_identity(org_id:int,user_id:int,db:SessionDep,admin:Admin):
    if not db.scalar(select(Membership.id).where(Membership.organization_id==org_id,Membership.user_id==user_id)):
        raise HTTPException(404,'Member not found')
    try:verify_target(db,user_id)
    except HTTPException as error:
        if error.status_code!=422:raise
        return {'verified':False,'detail':'Active linked identity with confirmed matching email required'}
    return {'verified':True}


@router.get('/organizations/{org_id}/invitations')
def invitations(org_id:int,db:SessionDep,admin:Admin,offset:int=Query(0,ge=0)):
    if not db.get(Organization,org_id):raise HTTPException(404,'Business not found')
    # Explicitly bounded platform metadata, not a tenant ORM/CRM access bypass.
    t=OrganizationInvitation.__table__
    return [dict(r) for r in db.connection().execute(select(t.c.id,t.c.email,t.c.name,t.c.role,t.c.expires_at).where(
        t.c.organization_id==org_id,t.c.status=='pending',t.c.expires_at>utcnow()).order_by(t.c.id).offset(offset).limit(100)).mappings()]


class Revocation(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    reason:str=Field(min_length=1,max_length=500)


@router.put('/organizations/{org_id}/members/{user_id}/revoke')
def revoke_member(org_id:int,user_id:int,body:Revocation,db:SessionDep,admin:Admin,request:Request):
    lock_administration(db);authorize(db,request,admin)
    if not db.scalar(select(Organization).where(Organization.id==org_id).with_for_update()):
        raise HTTPException(404,'Business not found')
    m=Membership.__table__;u=User.__table__;i=OrganizationInvitation.__table__
    conn=db.connection()
    target=conn.execute(select(m).where(m.c.organization_id==org_id,m.c.user_id==user_id).with_for_update()).mappings().first()
    if not target:raise HTTPException(404,'Member not found')
    user=db.get(User,user_id)
    if target['is_active'] and target['removed_at'] is None and user.is_active and target['role']=='owner':
        owners=conn.scalar(select(func.count()).select_from(m.join(u,m.c.user_id==u.c.id)).where(
            m.c.organization_id==org_id,m.c.role=='owner',m.c.is_active.is_(True),m.c.removed_at.is_(None),u.c.is_active.is_(True)))
        if owners<=1:raise HTTPException(409,'The final active owner cannot lose ownership or access')
    # Revoke only this membership, its tenant sessions and related pending invites.
    # No global User/Auth mutation and no access to customer CRM rows.
    conn.execute(update(m).where(m.c.id==target['id'],m.c.organization_id==org_id).values(is_active=False))
    db.execute(delete(AuthSession).where(AuthSession.user_id==user_id,AuthSession.active_organization_id==org_id))
    conn.execute(update(i).where(i.c.organization_id==org_id,i.c.status=='pending',
        or_(i.c.invited_by==user_id,func.lower(i.c.email)==user.email.lower())).values(status='revoked'))
    audit(db,admin.id,'membership_revoked',org_id,f'Member {user_id}: {body.reason}')
    db.commit();return {'ok':True}


@router.put('/organizations/{org_id}/invitations/{invitation_id}/revoke')
def revoke_invitation(org_id:int,invitation_id:int,body:Revocation,db:SessionDep,admin:Admin,request:Request):
    lock_administration(db);authorize(db,request,admin)
    if not db.scalar(select(Organization).where(Organization.id==org_id).with_for_update()):
        raise HTTPException(404,'Business not found')
    t=OrganizationInvitation.__table__
    changed=db.connection().execute(update(t).where(t.c.organization_id==org_id,t.c.id==invitation_id,t.c.status=='pending').values(status='revoked'))
    if not changed.rowcount:raise HTTPException(404,'Pending invitation not found')
    audit(db,admin.id,'invitation_revoked',org_id,f'Invitation {invitation_id}: {body.reason}')
    db.commit();return {'ok':True}

class Suspension(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    is_suspended:bool
    reason:str=Field(min_length=1,max_length=500)

@router.put('/organizations/{org_id}')
def suspend(org_id:int,body:Suspension,db:SessionDep,admin:Admin,request:Request):
    lock_administration(db);authorize(db,request,admin)
    org=db.scalar(select(Organization).where(Organization.id==org_id).with_for_update())
    if not org:raise HTTPException(404,'Business not found')
    org.is_suspended=body.is_suspended
    if body.is_suspended:
        db.execute(delete(AuthSession).where(AuthSession.active_organization_id==org.id))
    audit(db,admin.id,'business_suspended' if body.is_suspended else 'business_reactivated',org.id,body.reason)
    db.commit();return {'ok':True}

@router.get('/administrators')
def administrators(db:SessionDep,admin:Admin):
    return [{'user_id':p.user_id,'name':u.name,'email':u.email,'is_active':p.is_active and u.is_active and p.auth_user_id==u.auth_user_id}
        for p,u in db.execute(select(PlatformAdministrator,User).join(User)).all()]

class AdminChange(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    is_active:bool
    reason:str=Field(min_length=1,max_length=500)

@router.put('/administrators/{user_id}')
def change_admin(user_id:int,body:AdminChange,db:SessionDep,admin:Admin,request:Request):
    lock_administration(db);authorize(db,request,admin)
    target=db.get(PlatformAdministrator,user_id)
    if body.is_active:
        user=verify_target(db,user_id)
        if target:target.is_active=True;target.auth_user_id=user.auth_user_id
        else:db.add(PlatformAdministrator(user_id=user_id,auth_user_id=user.auth_user_id,is_active=True))
    else:
        if not target:raise HTTPException(404,'Platform administrator not found')
        active=db.scalars(select(PlatformAdministrator.user_id).join(User).where(PlatformAdministrator.is_active.is_(True),User.is_active.is_(True),PlatformAdministrator.auth_user_id==User.auth_user_id)).all()
        if user_id in active and len(active)<=1:raise HTTPException(409,'The final active platform administrator cannot be revoked')
        target.is_active=False
    audit(db,admin.id,'administrator_granted' if body.is_active else 'administrator_revoked',user_id,body.reason)
    db.commit();return {'ok':True}

@router.get('/activity')
def activity(db:SessionDep,admin:Admin):
    return [{'id':a.id,'actor_id':a.actor_id,'action':a.action,'target_id':a.target_id,'reason':a.reason,'created_at':a.created_at}
        for a in db.scalars(select(PlatformAudit).order_by(PlatformAudit.id.desc()).limit(50))]
