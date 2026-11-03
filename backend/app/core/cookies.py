from fastapi import Request

from app.core.config import settings


def session_cookie_samesite(request: Request) -> str:
    """Use cross-site cookies only for the explicitly approved desktop origin."""
    if request.headers.get("origin") in settings.DESKTOP_APP_ORIGINS:
        return "none"
    return settings.SESSION_COOKIE_SAMESITE.lower()


def session_cookie_secure(request: Request) -> bool:
    """Desktop cookies are always Secure because their approved origin is HTTPS."""
    return request.headers.get("origin") in settings.DESKTOP_APP_ORIGINS or settings.COOKIE_SECURE
