from datetime import timedelta
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from uuid import UUID
from sqlalchemy import select, delete, func
from app.api.deps import SessionDep, CurrentActiveUser, CurrentUser, active_membership, TenantUser
from app.core.config import settings
from app.core.security import verify_password, create_access_token
from app.core.provider import auth_request
from app.core.sessions import create_session, current_session, session_key, decrypt, revoke_user_sessions
from app.core.rate_limit import limit_auth
from app.crud.user import get_user_by_email, create_user
from app.crud.audit_log import log_event
from app.models.role import Role
from app.models.user import User
from app.models.session import AuthSession
from app.schemas.auth import UserRegister
from app.schemas.user import UserResponse
from app.services.onboarding import registration_enabled, remember_signup, signup_identity, verified_creator, create_workspace

router=APIRouter(prefix="/auth",tags=["auth"])

class EmailRequest(BaseModel):
    email: EmailStr

class RecoveryVerify(BaseModel):
    token_hash: str
    type: str = "recovery"

class PasswordChange(BaseModel):
    password: str
    current_password: str | None = None
    _validate_password = field_validator("password")(UserRegister.secure_password.__func__)

def linked_user(db, identity):
    if not identity.get("id"):
        raise HTTPException(401,"Invalid provider identity")
    user=db.scalar(select(User).where(User.auth_user_id==identity.get("id")))
    if not user and identity.get("email_confirmed_at") and identity.get("email"):
        from app.models.invitation import OrganizationInvitation
        from app.core.sessions import utcnow
        from app.core.security import hash_password
        import secrets
        invitation=db.connection().execute(select(OrganizationInvitation.__table__).where(
            OrganizationInvitation.email==identity["email"].lower(),
            OrganizationInvitation.provider_user_id==identity["id"],
            OrganizationInvitation.status=="pending",OrganizationInvitation.expires_at>utcnow())).mappings().first()
        signup = signup_identity(db, identity) if not invitation else None
        if invitation or signup:
            candidates=db.scalars(select(User).where(func.lower(User.email)==identity["email"].lower()).with_for_update()).all()
            if len(candidates)>1:raise HTTPException(409,"Ambiguous account email requires review")
            user=candidates[0] if candidates else None
            if user and user.auth_user_id not in {None,identity["id"]}:
                raise HTTPException(401,"Provider identity does not match the existing account")
            if user and signup:
                raise HTTPException(409,"Existing accounts must sign in or use an administrator invitation")
            if not user:
                role=db.scalar(select(Role).where(Role.name=="viewer"))
                if not role:raise HTTPException(503,"Workspace roles are not initialized")
                user=User(name=(invitation or signup)["name"],email=identity["email"].lower(),auth_user_id=identity["id"],
                    password_hash=hash_password(secrets.token_urlsafe(40)),role_id=role.id,is_active=True)
                db.add(user)
            elif user.is_active:
                user.auth_user_id=identity["id"]
            db.commit()
    if not user or not user.is_active or not identity.get("email_confirmed_at"):
        raise HTTPException(401,"This account is not active in this workspace. Contact your administrator.")
    return user

@router.get("/config")
def auth_config():
    return {"provider":settings.AUTH_PROVIDER,"recovery_available":settings.AUTH_PROVIDER=="supabase",
            "session_hours":settings.SESSION_HOURS,"remember_days":settings.REMEMBER_DAYS,"sso_available":False,
            "business_registration_enabled":registration_enabled()}

class BusinessSignup(UserRegister):
    model_config = ConfigDict(extra="forbid")

@router.post("/business-signup")
def business_signup(body:BusinessSignup,db:SessionDep,request:Request):
    if not registration_enabled():
        raise HTTPException(403,"Business registration is unavailable")
    email=str(body.email).lower()
    limit_auth(db,request,email,"business-signup")
    # Preserve all existing account links, roles and invitations; do not reveal
    # whether an account exists through this public response.
    existing=db.scalar(select(User.id).where(func.lower(User.email)==email))
    if not existing:
        data=auth_request("POST","/signup?redirect_to="+quote(settings.FRONTEND_URL.rstrip('/')+"/login",safe=""),
            {"email":email,"password":body.password})
        if data.get("access_token") or data.get("session"):
            raise HTTPException(503,"Enable email confirmation in the identity provider before registration")
        remember_signup(db,data.get("user",data),body.name,email)
    return {"message":"Check your email to verify your account, then sign in. Existing accounts can sign in normally."}

class BusinessDetails(BaseModel):
    model_config = ConfigDict(extra="forbid",str_strip_whitespace=True)
    name: str = Field(min_length=1,max_length=100)
    request_key: UUID

@router.get("/onboarding")
def onboarding_status(db:SessionDep,request:Request,current_user:CurrentUser):
    verified_creator(db,request,current_user)
    return {"can_create":True}

@router.post("/onboarding")
def provision_business(body:BusinessDetails,db:SessionDep,request:Request,current_user:CurrentUser):
    session=verified_creator(db,request,current_user)
    limit_auth(db,request,current_user.email,"provision-business")
    return create_workspace(db,current_user,session,body.name,str(body.request_key))

@router.post("/register",response_model=UserResponse)
def register(user_in:UserRegister,db:SessionDep,request:Request):
    if not settings.ALLOW_SELF_REGISTRATION or settings.AUTH_PROVIDER!="legacy":
        raise HTTPException(403,"Ask your administrator for an invitation")
    limit_auth(db,request,user_in.email,"register")
    if get_user_by_email(db,user_in.email.lower()):
        raise HTTPException(409,"An account with this email already exists")
    role=db.scalar(select(Role).where(Role.name=="sales_rep"))
    if not role:
        raise HTTPException(503,"Workspace has not been initialized")
    user_in.email=user_in.email.lower()
    user=create_user(db,user_in,role.id)
    log_event(db,"User Created",user.id,"User",user.id,"Account registered")
    return user

@router.post("/login")
def login(db:SessionDep,request:Request,response:Response,form:OAuth2PasswordRequestForm=Depends()):
    limit_auth(db,request,form.username)
    remember=request.query_params.get("remember")=="true"
    provider=None
    if settings.AUTH_PROVIDER=="supabase":
        provider=auth_request("POST","/token?grant_type=password",{"email":form.username,"password":form.password})
        user=linked_user(db,provider.get("user",{}))
    else:
        user=get_user_by_email(db,form.username.lower())
        if not user or not verify_password(form.password,user.password_hash) or not user.is_active:
            raise HTTPException(401,"Incorrect email or password")
    previous=request.cookies.get(settings.SESSION_COOKIE_NAME)
    if previous:
        db.execute(delete(AuthSession).where(AuthSession.id==session_key(previous)))
    create_session(db,response,user,remember,provider)
    log_event(db,"Login",user.id,"User",user.id,"User signed in")
    principal = user
    if db.info.get("organization_id"):
        principal = TenantUser(user, active_membership(db,user.id,db.info["organization_id"]))
    result={"user":UserResponse.model_validate(principal).model_dump(mode="json"),"token_type":"cookie",
            "expires_in":(settings.REMEMBER_DAYS*86400 if remember else settings.SESSION_HOURS*3600)}
    if settings.AUTH_PROVIDER=="legacy" and settings.ENVIRONMENT!="production":
        result.update(access_token=create_access_token(user.id,expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)),token_type="bearer")
    return result

@router.get("/me",response_model=UserResponse)
def me(current_user:CurrentActiveUser):
    return current_user

@router.get('/platform-access')
def platform_access(db:SessionDep,request:Request,current_user:CurrentUser):
    from app.services.platform import authorize
    try:authorize(db,request,current_user)
    except HTTPException as error:
        if error.status_code!=403:raise
        return {'is_platform_admin':False}
    return {'is_platform_admin':True}

class OrganizationSelection(BaseModel):
    organization_id: int

@router.get("/organizations")
def organizations(db:SessionDep,current_user:CurrentUser):
    from app.models.membership import Membership
    from app.models.organization import Organization
    if not settings.TENANT_ISOLATION_ENABLED or not current_user.is_active:
        raise HTTPException(403,"Organization selection is unavailable")
    return [{"id":o.id,"name":o.name} for o in db.scalars(select(Organization).join(Membership).where(
        Membership.user_id==current_user.id,Membership.is_active.is_(True),Membership.removed_at.is_(None),Organization.is_suspended.is_(False))).all()]

@router.post("/organization")
def select_organization(body:OrganizationSelection,db:SessionDep,request:Request,current_user:CurrentUser):
    if not settings.TENANT_ISOLATION_ENABLED or not current_user.is_active:
        raise HTTPException(403,"Organization selection is unavailable")
    session=getattr(request.state,"auth_session",None)
    if not session or session.recovery:
        raise HTTPException(403,"A normal cookie session is required")
    active_membership(db,current_user.id,body.organization_id)
    session.active_organization_id=body.organization_id
    db.commit()
    return {"organization_id":body.organization_id}

@router.post("/logout",status_code=204)
def logout(db:SessionDep,request:Request,response:Response):
    raw=request.cookies.get(settings.SESSION_COOKIE_NAME)
    if raw:
        session=db.get(AuthSession,session_key(raw))
        if session:
            if settings.AUTH_PROVIDER=="supabase" and session.access_token:
                try:
                    auth_request("POST","/logout?scope=local",token=decrypt(session.access_token))
                except HTTPException:
                    pass
            db.delete(session)
            db.commit()
    response.delete_cookie(settings.SESSION_COOKIE_NAME,path="/api",secure=settings.COOKIE_SECURE,httponly=True,samesite="lax")

@router.post("/forgot-password")
def forgot(body:EmailRequest,db:SessionDep,request:Request):
    limit_auth(db,request,body.email,"recovery")
    if settings.AUTH_PROVIDER!="supabase":
        raise HTTPException(503,"Account recovery requires the configured production identity provider")
    try:
        auth_request("POST","/recover?redirect_to="+quote(settings.FRONTEND_URL.rstrip('/')+"/login",safe=""),{"email":str(body.email)})
    except HTTPException as error:
        if error.status_code>=500 or error.status_code==429:
            raise
    return {"message":"If this account exists, a recovery email will arrive shortly."}

@router.post("/recovery/verify")
def recovery(body:RecoveryVerify,db:SessionDep,request:Request,response:Response):
    limit_auth(db,request,"recovery-link","verify")
    if settings.AUTH_PROVIDER!="supabase" or body.type not in {"recovery","invite","magiclink","email","signup"}:
        raise HTTPException(400,"Invalid recovery link")
    data=auth_request("POST","/verify",{"token_hash":body.token_hash,"type":body.type})
    user=linked_user(db,data.get("user",{}))
    recovery=body.type in {"recovery","invite"}
    create_session(db,response,user,provider=data,recovery=recovery)
    return {"message":"Link verified.","recovery":recovery}

@router.post("/password")
def change_password(body:PasswordChange,db:SessionDep,request:Request,response:Response,current_user:CurrentUser):
    # Account recovery is global authentication, not a CRM data request. A user
    # with several memberships must be able to recover before selecting a tenant.
    if not current_user.is_active:
        raise HTTPException(401,"Inactive user")
    if settings.AUTH_PROVIDER!="supabase":
        raise HTTPException(503,"Password changes require the production identity provider")
    session=current_session(db,request.cookies.get(settings.SESSION_COOKIE_NAME))
    if not session or not session.recovery:
        if not body.current_password:
            raise HTTPException(422,"Enter your current password")
        auth_request("POST","/token?grant_type=password",{"email":current_user.email,"password":body.current_password})
    if not session:
        raise HTTPException(401,"Please sign in again")
    auth_request("PUT","/user",{"password":body.password},token=decrypt(session.access_token))
    auth_request("POST","/logout?scope=global",token=decrypt(session.access_token))
    revoke_user_sessions(db,current_user.id)
    log_event(db,"Password Changed",current_user.id,"User",current_user.id,"Password changed using identity provider")
    response.delete_cookie(settings.SESSION_COOKIE_NAME,path="/api")
    return {"message":"Password updated. Please sign in again."}
