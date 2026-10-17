from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel,ConfigDict,EmailStr,Field
from sqlalchemy import select
from app.api.deps import CurrentActiveUser,CurrentUser,SessionDep
from app.services import team
from app.models import Membership,Organization
from app.models.invitation import OrganizationInvitation
from app.db.tenant_session import organization_id
from app.crud.audit_log import log_event
from app.core.config import settings

router=APIRouter(tags=["Team management"])
RoleName=Literal["owner","admin","sales_manager","sales_rep","viewer"]

class Invite(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=100)
    email:EmailStr
    role:RoleName="sales_rep"

class MemberUpdate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    role:RoleName|None=None
    is_active:bool|None=None

def invitation_data(row):
    return {key:getattr(row,key) for key in ("id","name","email","role","status","expires_at")}

@router.get('/team/members')
def members(db:SessionDep,actor:CurrentActiveUser):
    current=team.manager(db,actor)
    result=[]
    for m in db.scalars(select(Membership).where(Membership.organization_id==organization_id(db),Membership.removed_at.is_(None)).order_by(Membership.id)):
        result.append({"user_id":m.user_id,"name":m.user.name,"email":m.user.email,
            "role":m.role,"is_active":m.is_active,"is_self":m.user_id==actor.id,
            "can_manage":current.role=="owner" or m.role!="owner"})
    return {"members":result,"actor_role":current.role,"roles":team.ROLES if current.role=="owner" else team.ROLES[1:]}

@router.put('/team/members/{user_id}')
def update(user_id:int,body:MemberUpdate,db:SessionDep,actor:CurrentActiveUser):
    m=team.change_member(db,actor,user_id,role=body.role,is_active=body.is_active)
    log_event(db,"Member Updated",actor.id,"User",m.user_id,"Organization role or access updated")
    return {"user_id":m.user_id,"role":m.role,"is_active":m.is_active}

@router.delete('/team/members/{user_id}')
def remove(user_id:int,db:SessionDep,actor:CurrentActiveUser):
    team.change_member(db,actor,user_id,remove=True)
    log_event(db,"Member Removed",actor.id,"User",user_id,"Organization access removed; historical ownership preserved")
    return {"ok":True}

@router.get('/team/invitations')
def invitations(db:SessionDep,actor:CurrentActiveUser):
    current=team.manager(db,actor)
    return [invitation_data(r)|{"can_manage":current.role=="owner" or r.role!="owner"} for r in db.scalars(select(OrganizationInvitation).where(
        OrganizationInvitation.status=="pending",OrganizationInvitation.expires_at>datetime.now(timezone.utc)).order_by(OrganizationInvitation.id))]

@router.post('/team/invitations')
def invite(body:Invite,db:SessionDep,actor:CurrentActiveUser):
    return invitation_data(team.invite(db,actor,body.name,str(body.email),body.role))

@router.delete('/team/invitations/{invitation_id}')
def cancel(invitation_id:int,db:SessionDep,actor:CurrentActiveUser):
    current=team.manager(db,actor)
    row=db.get(OrganizationInvitation,invitation_id)
    if not row:raise HTTPException(404,"Invitation not found")
    if row.role=="owner" and current.role!="owner":raise HTTPException(403,"Only an owner can manage owner invitations")
    row.status="revoked"
    log_event(db,"Invitation Revoked",actor.id,"Invitation",row.id,"Pending invitation revoked")
    return {"ok":True}

@router.get('/auth/invitations')
def my_invitations(db:SessionDep,user:CurrentUser):
    if not settings.TENANT_ISOLATION_ENABLED:raise HTTPException(503,"Tenant access has not been activated")
    if not user.is_active:raise HTTPException(403,"An active account is required")
    if not user.auth_user_id:return []
    # Authentication bootstrap: expose only this verified recipient's invitations.
    rows=db.connection().execute(select(OrganizationInvitation.id,OrganizationInvitation.role,Organization.name.label("organization_name")).join(Organization).where(
        OrganizationInvitation.email==user.email.lower(),OrganizationInvitation.provider_user_id==user.auth_user_id,
        OrganizationInvitation.status=="pending",OrganizationInvitation.expires_at>datetime.now(timezone.utc))).mappings()
    return [dict(r) for r in rows]

@router.post('/auth/invitations/{invitation_id}/accept')
def accept(invitation_id:int,db:SessionDep,user:CurrentUser):
    if not settings.TENANT_ISOLATION_ENABLED:raise HTTPException(503,"Tenant access has not been activated")
    if not user.is_active or not user.auth_user_id:raise HTTPException(403,"A verified account is required")
    data=db.connection().execute(select(OrganizationInvitation.__table__).where(
        OrganizationInvitation.id==invitation_id,OrganizationInvitation.email==user.email.lower(),
        OrganizationInvitation.provider_user_id==user.auth_user_id)).mappings().first()
    if not data:raise HTTPException(404,"Invitation not found")
    db.scalar(select(Organization).where(Organization.id==data["organization_id"]).with_for_update())
    db.info.update(organization_id=data["organization_id"],actor_id=user.id)
    row=db.get(OrganizationInvitation,invitation_id,populate_existing=True)
    if row.status!="pending" or row.expires_at<=datetime.now(timezone.utc):
        raise HTTPException(409,"Invitation is expired or no longer pending")
    inviter=db.scalar(select(Membership).where(Membership.organization_id==row.organization_id,
        Membership.user_id==row.invited_by,Membership.is_active.is_(True),Membership.removed_at.is_(None)))
    if not inviter or not inviter.user.is_active or inviter.role not in {"owner","admin"} or (row.role=="owner" and inviter.role!="owner"):
        raise HTTPException(409,"Invitation authority has changed; request a new invitation")
    member=db.scalar(select(Membership).where(Membership.organization_id==row.organization_id,Membership.user_id==user.id))
    if member and member.is_active and not member.removed_at:raise HTTPException(409,"Already an active member")
    from app.services.subscriptions import check_seat
    check_seat(db,row.organization_id,exclude_invitation=row.id)
    if not member:
        member=Membership(organization_id=row.organization_id,user_id=user.id,role=row.role,is_active=True)
        db.add(member)
    else:
        member.role=row.role;member.permission_role_name="admin" if row.role=="owner" else row.role
        member.is_active=True;member.removed_at=None
    row.status="accepted"
    db.flush()
    log_event(db,"Invitation Accepted",user.id,"Invitation",row.id,"Verified employee accepted organization access")
    return {"organization_id":row.organization_id}
