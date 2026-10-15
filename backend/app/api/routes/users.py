from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from sqlalchemy import select
from app.models.role import Role
from app.models.user import User
from app.core.config import settings
from app.core.provider import auth_request
from app.core.sessions import revoke_user_sessions
from app.schemas.auth import UserRegister
from app.core.security import hash_password
import secrets
from uuid import UUID
from app.api.deps import SessionDep, CurrentActiveUser, require_role
from app.schemas.user import UserResponse, UserUpdate, UserUpdateAdmin
from app.crud.user import update_user, get_user_by_id, get_users
from app.crud.audit_log import log_event

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserResponse)
def read_user_me(current_user: CurrentActiveUser) -> Any:
    return current_user

@router.put("/me", response_model=UserResponse)
def update_user_me(
    user_in: UserUpdate, current_user: CurrentActiveUser, db: SessionDep
) -> Any:
    if user_in.email and user_in.email.lower() != current_user.email.lower():
        raise HTTPException(422,"Email changes require your identity provider administrator")
    if user_in.preferences is not None:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        allowed={"timezone","compact_view","weekly_digest"}
        if set(user_in.preferences)-allowed:
            raise HTTPException(422,"Unsupported preference")
        try:
            ZoneInfo(user_in.preferences.get("timezone","UTC"))
        except (ZoneInfoNotFoundError,TypeError):
            raise HTTPException(422,"Use a valid IANA timezone")
        for flag in ["compact_view","weekly_digest"]:
            if flag in user_in.preferences and not isinstance(user_in.preferences[flag],bool):
                raise HTTPException(422,"Preference must be true or false")
        user_in.preferences={**(current_user.preferences or {}),**user_in.preferences}
    result=update_user(db,db_user=current_user,user_in=user_in)
    log_event(db,"Profile Updated",current_user.id,"User",current_user.id,"Profile or preferences updated")
    return result

# Administrator endpoints
@router.get("", response_model=List[UserResponse], dependencies=[Depends(require_role(["admin"]))])
def read_users(db: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    return get_users(db, skip=skip, limit=limit)

@router.get("/{user_id}", response_model=UserResponse, dependencies=[Depends(require_role(["admin"]))])
def read_user_by_id(user_id: int, db: SessionDep) -> Any:
    user = get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}", response_model=UserResponse, dependencies=[Depends(require_role(["admin"]))])
def update_user_by_id(
    user_id: int, user_in: UserUpdateAdmin, db: SessionDep, current_user: CurrentActiveUser
) -> Any:
    user = get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user_in.role_id is not None and not db.get(Role,user_in.role_id):
        raise HTTPException(422,"Role does not exist")
    if user_in.email and user_in.email.lower()!=user.email.lower():
        raise HTTPException(422,"Email changes require your identity provider administrator")
    if user_id==current_user.id and (user_in.is_active is False or (user_in.role_id and user_in.role_id!=current_user.role_id)):
        raise HTTPException(409,"Ask another administrator to change your own access")
    result=update_user(db,db_user=user,user_in=user_in)
    if user_in.is_active is False or user_in.role_id is not None:
        revoke_user_sessions(db,user.id)
    log_event(db,"User Updated",current_user.id,"User",user.id,"User profile, role or access updated")
    return result

@router.patch("/{user_id}/status", response_model=UserResponse, dependencies=[Depends(require_role(["admin"]))])
def change_user_status(
    user_id: int, is_active: bool, db: SessionDep, current_user: CurrentActiveUser
) -> Any:
    user = get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_id==current_user.id and not is_active:
        raise HTTPException(409,"Ask another administrator to deactivate your account")
    update_data = UserUpdateAdmin(is_active=is_active)
    updated_user = update_user(db, db_user=user, user_in=update_data)
    log_event(db, action="User Status Changed", user_id=current_user.id, entity="User", entity_id=user.id, description=f"User {user.email} active status changed to {is_active}")
    if not is_active:
        revoke_user_sessions(db,user.id)
    return updated_user

class InviteUser(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True,extra='forbid')
    name: str=Field(min_length=1,max_length=100)
    email: EmailStr
    role_id: int
    password: str | None=None

class LinkExistingIdentity(BaseModel):
    auth_user_id: UUID | None=None

@router.post('/{user_id}/invite',response_model=UserResponse,dependencies=[Depends(require_role(['admin']))])
def invite_existing_user(user_id:int,body:LinkExistingIdentity,db:SessionDep,current_user:CurrentActiveUser):
    if settings.AUTH_PROVIDER!='supabase':raise HTTPException(503,'Configure Supabase Auth before migrating an account')
    user=db.get(User,user_id)
    if not user:raise HTTPException(404,'User not found')
    if not user.is_active:raise HTTPException(409,'Activate this account before sending an invitation')
    if user.auth_user_id:raise HTTPException(409,'This account already has a provider identity')
    if body.auth_user_id:
        identity=auth_request('GET','/admin/users/'+str(body.auth_user_id),admin=True)
        if identity.get('email','').lower()!=user.email.lower() or not identity.get('email_confirmed_at'):
            raise HTTPException(422,'Choose a verified provider account with exactly the same email')
    else:
        from urllib.parse import quote
        identity=auth_request('POST','/invite?redirect_to='+quote(settings.FRONTEND_URL.rstrip('/')+'/login',safe=''),{'email':user.email,'data':{'name':user.name}},admin=True)
    user.auth_user_id=identity['id'];db.commit()
    revoke_user_sessions(db,user.id)
    log_event(db,'User Identity Linked',current_user.id,'User',user.id,'Existing ownership and role preserved during provider migration')
    return user

@router.post("",response_model=UserResponse,dependencies=[Depends(require_role(["admin"]))])
def invite_user(body:InviteUser,db:SessionDep,current_user:CurrentActiveUser):
    if not db.get(Role,body.role_id):
        raise HTTPException(422,"Role does not exist")
    if db.scalar(select(User).where(User.email==str(body.email).lower())):
        raise HTTPException(409,"An account with this email already exists")
    provider_id=None
    if settings.AUTH_PROVIDER=="supabase":
        identity=auth_request("POST","/invite",{"email":str(body.email),"data":{"name":body.name}},admin=True)
        provider_id=identity["id"]
    elif body.password:
        try:
            UserRegister.secure_password(body.password)
        except ValueError as error:
            raise HTTPException(422,str(error))
    else:
        raise HTTPException(422,"Development account creation requires a password")
    user=User(name=body.name.strip(),email=str(body.email).lower(),role_id=body.role_id,is_active=True,
              auth_user_id=provider_id,password_hash=hash_password(body.password if settings.AUTH_PROVIDER=='legacy' and body.password else secrets.token_urlsafe(36)))
    db.add(user)
    db.commit()
    db.refresh(user)
    log_event(db,"User Invited",current_user.id,"User",user.id,"Account provisioned for workspace")
    return user
