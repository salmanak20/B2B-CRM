from typing import Annotated,Literal
from fastapi import APIRouter,Depends,Request,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,func,delete
from app.api.deps import SessionDep,CurrentUser
from app.models import Organization,Membership,User
from app.models.platform import PlatformAdministrator,PlatformAudit
from app.models.session import AuthSession
from app.services.platform import authorize,verify_target,lock_administration,audit

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
    total=db.scalar(select(func.count()).select_from(Organization))
    suspended=db.scalar(select(func.count()).select_from(Organization).where(Organization.is_suspended.is_(True)))
    return {'businesses':total,'active':total-suspended,'suspended':suspended,'memberships':db.scalar(select(func.count()).select_from(Membership))}

@router.get('/organizations')
def organizations(db:SessionDep,admin:Admin,q:str=Query('',max_length=100),status:Literal['all','active','suspended']='all',offset:int=Query(0,ge=0)):
    stmt=select(Organization).where(Organization.name.ilike('%'+q+'%'))
    if status!='all':stmt=stmt.where(Organization.is_suspended.is_(status=='suspended'))
    return [{'id':o.id,'name':o.name,'slug':o.slug,'is_suspended':o.is_suspended} for o in db.scalars(stmt.order_by(Organization.id).offset(offset).limit(100))]

@router.get('/organizations/{org_id}')
def details(org_id:int,db:SessionDep,admin:Admin):
    org=db.get(Organization,org_id)
    if not org:raise HTTPException(404,'Business not found')
    return org_summary(db,org)

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
