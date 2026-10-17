"""No business-record reads or tenant bypasses belong in this service."""
from fastapi import HTTPException
from sqlalchemy import select,func,text
from app.models import User
from app.models.platform import PlatformAdministrator,PlatformAudit
from app.core.provider import auth_request
from app.core.config import settings
from app.core.sessions import decrypt

def lock_administration(db):
    # One shared transaction lock protects bootstrap, grants and final-admin checks.
    db.connection().execute(text('SELECT pg_advisory_xact_lock(5052026)'))

def verify_target(db,user_id):
    user=db.scalar(select(User).where(User.id==user_id).with_for_update())
    if not user or not user.is_active or not user.auth_user_id:
        raise HTTPException(422,'An active, linked existing user is required')
    if settings.AUTH_PROVIDER!='supabase':raise HTTPException(503,'Supabase verification is required')
    identity=auth_request('GET','/admin/users/'+user.auth_user_id,admin=True)
    identity=identity.get('user',identity)
    if identity.get('id')!=user.auth_user_id or not identity.get('email_confirmed_at') or str(identity.get('email','')).lower()!=user.email.lower():
        raise HTTPException(422,'The existing user identity must have a verified matching email')
    return user

def authorize(db,request,user):
    session=getattr(request.state,'auth_session',None)
    admin=db.get(PlatformAdministrator,user.id,populate_existing=True)
    if not user.is_active or not admin or not admin.is_active or admin.auth_user_id!=user.auth_user_id or not session or session.recovery or settings.AUTH_PROVIDER!='supabase':
        raise HTTPException(403,'Platform administrator access required')
    identity=auth_request('GET','/user',token=decrypt(session.access_token))
    if identity.get('id')!=admin.auth_user_id or not identity.get('email_confirmed_at'):
        raise HTTPException(403,'Verified platform administrator session required')
    return user

def audit(db,actor,action,target,reason):
    db.add(PlatformAudit(actor_id=actor,action=action,target_id=target,reason=reason))

def bootstrap(db,user_id,email,auth_user_id):
    try:
        lock_administration(db)
        if db.scalar(select(func.count()).select_from(PlatformAdministrator)):
            raise HTTPException(409,'Bootstrap is closed; use existing platform administrator management')
        user=verify_target(db,user_id)
        if user.email.lower()!=email.lower() or user.auth_user_id!=auth_user_id:
            raise HTTPException(422,'Explicit bootstrap identity does not match')
        db.add(PlatformAdministrator(user_id=user.id,auth_user_id=user.auth_user_id,is_active=True))
        audit(db,user.id,'administrator_bootstrap',user.id,'Explicit verified operator bootstrap')
        db.commit()
    except Exception:
        db.rollback();raise
