"""Bind default-template recovery codes to the browser that requested them."""
import base64
import hashlib
import json
import secrets
from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from app.core.config import settings
from app.core.sessions import cipher

RECOVERY_TTL = 3600


def cookie_name():
    return settings.SESSION_COOKIE_NAME + "_recovery"


def start_recovery(email):
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = cipher().encrypt(json.dumps({"purpose": "recovery", "email": email, "verifier": verifier}).encode()).decode()
    return challenge, state


def save_recovery(response, state):
    response.set_cookie(cookie_name(), state, max_age=RECOVERY_TTL, path="/api/v1/auth",
                        secure=settings.COOKIE_SECURE, httponly=True, samesite=settings.SESSION_COOKIE_SAMESITE.lower())
    response.headers["Cache-Control"] = "no-store"


def read_recovery(request):
    try:
        state = json.loads(cipher().decrypt(request.cookies.get(cookie_name(), "").encode(), ttl=RECOVERY_TTL))
        if state.get("purpose") != "recovery" or not state.get("email") or not state.get("verifier"):
            raise ValueError()
        return state
    except (InvalidToken, ValueError, TypeError, AttributeError):
        raise HTTPException(400, "Request a new recovery email and open its link in the same browser.")


def clear_recovery(response):
    response.delete_cookie(cookie_name(), path="/api/v1/auth", secure=settings.COOKIE_SECURE,
                           httponly=True, samesite=settings.SESSION_COOKIE_SAMESITE.lower())
