"""Organization membership administration; never mutate a shared global role."""
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, delete, func, or_
from app.core.config import settings
from app.core.provider import auth_request
from app.core.sessions import revoke_user_sessions
from app.models import Membership, Organization, User
from app.models.invitation import OrganizationInvitation
from app.models.session import AuthSession
from app.db.tenant_session import organization_id
from app.crud.audit_log import log_event

ROLES=("owner","admin","sales_manager","sales_rep","viewer")


def manager(db,actor):
    org=organization_id(db)
    db.scalar(select(Organization).where(Organization.id==org).with_for_update())
    current=db.scalar(select(Membership).where(Membership.organization_id==org,
        Membership.user_id==actor.id).execution_options(populate_existing=True))
    if not current or not current.is_active or current.removed_at or current.role not in {"owner","admin"}:
        raise HTTPException(403,"Organization owner or administrator access is required")
    return current


def change_member(db,actor,user_id,*,role=None,is_active=None,remove=False):
    current=manager(db,actor)
    target=db.scalar(select(Membership).where(Membership.organization_id==organization_id(db),Membership.user_id==user_id).with_for_update())
    if not target or target.removed_at:
        raise HTTPException(404,"Member not found")
    if role is not None and role not in ROLES:
        raise HTTPException(422,"Invalid organization role")
    if current.role!="owner" and (role=="owner" or target.role=="owner"):
        raise HTTPException(403,"Only an owner can manage owner permissions")
    loses_ownership=target.role=="owner" and (role not in {None,"owner"} or is_active is False or remove)
    if target.is_active and target.user.is_active and loses_ownership:
        count=db.scalar(select(func.count(Membership.id)).join(User).where(
            Membership.organization_id==organization_id(db),Membership.role=="owner",
            Membership.is_active.is_(True),Membership.removed_at.is_(None),User.is_active.is_(True)))
        if count<=1:
            raise HTTPException(409,"The final active owner cannot lose ownership or access")
    if is_active is True and not target.is_active:
        from app.services.subscriptions import check_seat
        check_seat(db,organization_id(db))
    prior_role=target.role
    if role is not None:
        target.role=role
        target.permission_role_name="admin" if role=="owner" else role
    if is_active is not None: target.is_active=is_active
    if remove:
        target.is_active=False
        target.removed_at=datetime.now(timezone.utc)
    if not target.is_active:
        db.execute(delete(AuthSession).where(AuthSession.user_id==user_id,
            AuthSession.active_organization_id==organization_id(db)))
        # Invalidate old pending invitations as well as the current membership.
        user=db.get(User,user_id)
        if user:
            for invitation in db.scalars(select(OrganizationInvitation).where(
                    or_(OrganizationInvitation.email==user.email.lower(),OrganizationInvitation.invited_by==user_id),OrganizationInvitation.status=="pending")):
                invitation.status="revoked"
    elif role is not None and (role not in {"owner","admin"} or (prior_role=="owner" and role!="owner")):
        pending=select(OrganizationInvitation).where(OrganizationInvitation.invited_by==user_id,OrganizationInvitation.status=="pending")
        if role=="admin":pending=pending.where(OrganizationInvitation.role=="owner")
        for invitation in db.scalars(pending):invitation.status="revoked"
    db.flush()
    return target


def global_identity(db,email):
    # Users are global auth identities. This bounded internal lookup never exposes
    # another tenant's profile or grants membership; acceptance requires that user.
    identities=db.connection().execute(select(User.id,User.auth_user_id,User.email).where(func.lower(User.email)==email)).mappings().all()
    if len(identities)>1:raise HTTPException(409,"Ambiguous account email requires review")
    return identities[0] if identities else None


def send_invitation(email,name,existing):
    if settings.AUTH_PROVIDER!="supabase":
        raise HTTPException(503,"Employee invitations require configured Supabase Auth")
    redirect=quote(settings.FRONTEND_URL.rstrip('/')+'/login',safe='')
    if existing and existing["auth_user_id"]:
        identity=auth_request("GET","/admin/users/"+existing["auth_user_id"],admin=True)
        if identity.get("id")!=existing["auth_user_id"] or identity.get("email","").lower()!=email:
            raise HTTPException(409,"Provider identity does not match invitation email")
        auth_request("POST","/otp?redirect_to="+redirect,{"email":email,"create_user":False})
    else:
        identity=auth_request("POST","/invite?redirect_to="+redirect,{"email":email,"data":{"name":name}},admin=True)
    try: provider_id=str(UUID(identity["id"]))
    except (KeyError,ValueError,TypeError): raise HTTPException(502,"Invalid invitation provider identity")
    if identity.get("email","").lower()!=email:
        raise HTTPException(502,"Invitation provider email mismatch")
    return provider_id


def invite(db,actor,name,email,role):
    current=manager(db,actor)
    if role not in ROLES or (role=="owner" and current.role!="owner"):
        raise HTTPException(403,"Only an owner may invite another owner")
    email=email.lower()
    existing=global_identity(db,email)
    if existing:
        member=db.scalar(select(Membership).where(Membership.organization_id==organization_id(db),Membership.user_id==existing["id"]))
        if member and member.is_active and not member.removed_at:
            raise HTTPException(409,"This person is already an active member")
    row=db.scalar(select(OrganizationInvitation).where(OrganizationInvitation.email==email))
    now=datetime.now(timezone.utc)
    if row and row.status=="pending" and row.expires_at>now:
        raise HTTPException(409,"An invitation is already pending")
    from app.services.subscriptions import check_seat
    check_seat(db,organization_id(db))
    provider_id=send_invitation(email,name,existing)
    if not row:
        row=OrganizationInvitation(email=email,name=name,role=role,invited_by=actor.id,
            provider_user_id=provider_id,expires_at=now+timedelta(days=7),status="pending")
        db.add(row)
    else:
        row.name,row.role,row.invited_by=name,role,actor.id
        row.provider_user_id,row.expires_at,row.status=provider_id,now+timedelta(days=7),"pending"
    db.flush()
    log_event(db,"Employee Invited",actor.id,"Invitation",row.id,"Organization invitation created")
    return row
