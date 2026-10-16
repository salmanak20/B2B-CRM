from typing import Generator, Annotated, Callable
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from pydantic import ValidationError

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User
from app.schemas.auth import TokenPayload
from app.crud.user import get_user_by_id
from sqlalchemy import select
from app.models.membership import Membership


class TenantUser:
    """Request principal; never overwrite the global User.role relationship."""
    def __init__(self, user, membership):
        self.user = user
        self.membership = membership

    @property
    def role(self):
        return self.membership.permission_role

    @property
    def role_id(self):
        return self.role.id

    @property
    def organization_id(self):
        return self.membership.organization_id

    @property
    def is_active(self):
        return self.user.is_active and self.membership.is_active

    def __getattr__(self, name):
        return getattr(self.user, name)


def active_membership(db, user_id, org_id):
    member = db.scalar(select(Membership).where(Membership.user_id == user_id,
        Membership.organization_id == org_id, Membership.is_active.is_(True)).execution_options(populate_existing=True))
    if not member:
        raise HTTPException(403, "Active organization membership is required")
    return member


def resolve_tenant(db, user, request):
    if not settings.TENANT_ISOLATION_ENABLED:
        raise HTTPException(503, "Tenant access has not been activated")
    session = getattr(request.state, "auth_session", None)
    if session and session.recovery and request.url.path != "/api/v1/auth/password":
        raise HTTPException(403, "Complete account recovery before accessing CRM data")
    selected = request.headers.get("X-Organization-ID")
    if selected is not None:
        try:
            selected = int(selected)
            if selected <= 0: raise ValueError()
        except ValueError:
            raise HTTPException(403, "Invalid organization selection")
    elif session and session.active_organization_id is not None:
        selected = session.active_organization_id
    else:
        choices = db.scalars(select(Membership).where(Membership.user_id == user.id,
            Membership.is_active.is_(True))).all()
        if len(choices) != 1:
            raise HTTPException(403, "Select an authorized organization")
        selected = choices[0].organization_id
    member = active_membership(db, user.id, selected)
    db.info.update(organization_id=selected, actor_id=user.id)
    return TenantUser(user, member)

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"/api/v1/auth/login", auto_error=False
)

# get_db is already defined in app.db.session, but we can redefine or import it.
# Wait, let's just import it from app.db.session
from app.db.session import get_db

SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str | None, Depends(reusable_oauth2)]

def get_current_user(db: SessionDep, token: TokenDep, request: Request) -> User:
    from app.core.sessions import current_session
    raw = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if raw and not (token and settings.AUTH_PROVIDER == "legacy" and settings.ENVIRONMENT != "production"):
        session = current_session(db, raw)
        request.state.auth_session = session
        user = get_user_by_id(db, user_id=session.user_id)
        if not user:
            raise HTTPException(401, "Session expired")
        return user
    if not token or settings.ENVIRONMENT == "production" or settings.AUTH_PROVIDER != "legacy":
        raise HTTPException(401, "Please sign in")
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        token_data = TokenPayload(**payload)
        user_id = int(token_data.sub)
    except (jwt.PyJWTError, ValidationError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    user = get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Please sign in again")
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]

def get_current_active_user(current_user: CurrentUser, db: SessionDep, request: Request) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return resolve_tenant(db, current_user, request)

CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]

def require_role(required_roles: list[str]) -> Callable:
    def role_checker(current_user: CurrentActiveUser) -> User:
        if current_user.role.name not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

def require_permission(required_permission: str) -> Callable:
    def permission_checker(current_user: CurrentActiveUser) -> User:
        user_permissions = [p.name for p in current_user.role.permissions]
        if required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return permission_checker
