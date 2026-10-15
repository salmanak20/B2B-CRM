import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import delete, select
from app.core.config import settings
from app.core.provider import auth_request
from app.models.session import AuthSession
from app.models.user import User

def utcnow():
    return datetime.now(timezone.utc)

def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def session_key(value):
    return hashlib.sha256(value.encode()).hexdigest()

def cipher():
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.JWT_SECRET_KEY.encode()).digest()))

def encrypt(value):
    return cipher().encrypt(value.encode()).decode() if value else None

def decrypt(value):
    try:
        return cipher().decrypt(value.encode()).decode() if value else None
    except InvalidToken:
        raise HTTPException(401, "Session expired. Please sign in again.")

def create_session(db, response, user, remember=False, provider=None, recovery=False):
    raw = secrets.token_urlsafe(48)
    seconds = (settings.REMEMBER_DAYS * 86400 if remember else settings.SESSION_HOURS * 3600)
    session = AuthSession(id=session_key(raw), user_id=user.id, expires_at=utcnow()+timedelta(seconds=seconds), recovery=recovery)
    if provider:
        set_provider_tokens(session, provider)
    db.add(session)
    db.commit()
    response.set_cookie(settings.SESSION_COOKIE_NAME, raw, httponly=True, secure=settings.COOKIE_SECURE,
                        samesite="lax", path="/api", max_age=seconds if remember else None)
    response.headers["Cache-Control"] = "no-store"
    return session

def set_provider_tokens(session, data):
    session.access_token = encrypt(data["access_token"])
    session.refresh_token = encrypt(data["refresh_token"])
    session.access_expires_at = utcnow()+timedelta(seconds=data.get("expires_in",3600))

def current_session(db, raw):
    if not raw:
        return None
    session = db.scalar(select(AuthSession).where(AuthSession.id==session_key(raw)).with_for_update())
    if not session or aware(session.expires_at) <= utcnow():
        raise HTTPException(401, "Session expired. Please sign in again.")
    if settings.AUTH_PROVIDER == "supabase":
        if not session.access_token:
            raise HTTPException(401, "Please sign in again.")
        if aware(session.access_expires_at) <= utcnow()+timedelta(seconds=30):
            data = auth_request("POST", "/token?grant_type=refresh_token", {"refresh_token":decrypt(session.refresh_token)})
            set_provider_tokens(session,data)
            db.commit()
        identity = auth_request("GET", "/user", token=decrypt(session.access_token))
        user = db.get(User,session.user_id)
        if not user or identity.get("id") != user.auth_user_id:
            raise HTTPException(401,"Invalid session")
    return session

def revoke_user_sessions(db, user_id):
    db.execute(delete(AuthSession).where(AuthSession.user_id==user_id))
    db.commit()
