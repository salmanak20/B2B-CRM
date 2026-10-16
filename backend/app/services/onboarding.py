"""Auth bootstrap is unscoped; tenant context is set only to a newly created workspace."""
import re
import secrets
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.core.provider import auth_request
from app.core.sessions import decrypt
from app.models import User, Role, Organization, Membership
from app.models.onboarding import SignupIntent, OrganizationProvision
from app.models.workspace import WorkspaceSettings
from app.models.session import AuthSession
from app.core.sessions import utcnow, aware


def registration_enabled():
    return (settings.BUSINESS_REGISTRATION_ENABLED and settings.TENANT_ISOLATION_ENABLED
            and settings.AUTH_PROVIDER == "supabase"
            and (settings.ENVIRONMENT != "production" or settings.AUTH_EMAIL_CONFIGURATION_VERIFIED))


def remember_signup(db, identity, name, email):
    # A duplicate provider signup may return an obfuscated identity. It grants
    # nothing: login must independently verify this exact ID and email later.
    try:
        provider_id = str(UUID(identity.get("id", "")))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(502, "Invalid signup provider response")
    if str(identity.get("email", "")).lower() != email:
        raise HTTPException(502, "Invalid signup provider response")
    db.execute(insert(SignupIntent).values(provider_user_id=provider_id, email=email, name=name)
               .on_conflict_do_nothing(index_elements=["provider_user_id"]))
    db.commit()


def signup_identity(db, identity):
    intent = db.scalar(select(SignupIntent).where(SignupIntent.provider_user_id == identity["id"]).with_for_update())
    if not intent or intent.email != identity["email"].lower():
        return None
    return {"name": intent.name}


def verified_creator(db, request, user):
    session = getattr(request.state, "auth_session", None)
    if (not registration_enabled() or not user.is_active or not user.auth_user_id
            or not session or session.recovery or not session.access_token):
        raise HTTPException(403, "Verified business registration is unavailable")
    identity = auth_request("GET", "/user", token=decrypt(session.access_token))
    if (identity.get("id") != user.auth_user_id or not identity.get("email_confirmed_at")
            or str(identity.get("email", "")).lower() != user.email.lower()):
        raise HTTPException(403, "Verify your email before creating a workspace")
    return session


def create_workspace(db, user, session, name, request_key):
    previous = dict(db.info)
    try:
        # Serializes concurrent provisioning for this identity. No existing
        # organization or membership is adopted or promoted by this operation.
        creator = db.scalar(select(User).where(User.id == user.id).with_for_update()
                            .execution_options(populate_existing=True))
        if not creator or not creator.is_active:
            raise HTTPException(403, "Creator account is inactive")
        session = db.scalar(select(AuthSession).where(AuthSession.id == session.id,
            AuthSession.user_id == creator.id).with_for_update().execution_options(populate_existing=True))
        if not session or session.recovery or aware(session.expires_at) <= utcnow():
            raise HTTPException(401, "Please sign in again")
        receipt = db.scalar(select(OrganizationProvision).where(
            OrganizationProvision.user_id == user.id, OrganizationProvision.request_key == request_key))
        if receipt:
            if receipt.name != name:
                raise HTTPException(409, "This request was already used for different business details")
            member = db.scalar(select(Membership).where(Membership.user_id == user.id,
                Membership.organization_id == receipt.organization_id, Membership.is_active.is_(True),
                Membership.removed_at.is_(None)))
            if not member:
                raise HTTPException(403, "Workspace access has been revoked")
            session.active_organization_id = receipt.organization_id
            db.commit()
            return {"organization_id": receipt.organization_id}
        if not db.scalar(select(Role.id).where(Role.name == "admin")):
            raise HTTPException(503, "Workspace roles are not initialized")
        prefix = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:70] or "business"
        for attempt in range(3):
            try:
                with db.begin_nested():
                    organization = Organization(name=name, slug=prefix + "-" + secrets.token_hex(6))
                    db.add(organization)
                    db.flush()
                break
            except IntegrityError:
                if attempt == 2:
                    raise HTTPException(409, "Workspace slug unavailable; please retry")
        db.info.update(organization_id=organization.id, actor_id=user.id)
        db.add(Membership(organization_id=organization.id, user_id=user.id, role="owner", is_active=True))
        db.flush()
        db.add(WorkspaceSettings(organization_id=organization.id, name=name, timezone="UTC", currency="USD"))
        db.add(OrganizationProvision(user_id=user.id, request_key=request_key, name=name, organization_id=organization.id))
        session.active_organization_id = organization.id
        db.commit()
        return {"organization_id": organization.id}
    except Exception:
        db.rollback()
        db.info.clear()
        db.info.update(previous)
        raise
