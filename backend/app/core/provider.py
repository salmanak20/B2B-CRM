"""Supabase Auth REST adapter. All privileged keys and tokens stay on the server."""
import httpx
from fastapi import HTTPException
from app.core.config import settings

def auth_request(method, path, data=None, token=None, admin=False):
    key = settings.SUPABASE_SERVICE_ROLE_KEY if admin else settings.SUPABASE_PUBLISHABLE_KEY
    if not settings.SUPABASE_URL or not key:
        raise HTTPException(503, "Authentication provider is not configured. Contact your administrator.")
    headers = {"apikey": key}
    if token or admin:
        headers["Authorization"] = f"Bearer {token or key}"
    try:
        response = httpx.request(method, settings.SUPABASE_URL.rstrip("/") + "/auth/v1" + path,
                                headers=headers, json=data, timeout=15)
    except httpx.HTTPError:
        raise HTTPException(503, "Authentication service is temporarily unavailable. Please try again.")
    if response.is_error:
        if response.status_code == 429:
            raise HTTPException(429, "Too many attempts. Please try again later.")
        if response.status_code >= 500:
            raise HTTPException(503, "Authentication service is temporarily unavailable.")
        raise HTTPException(401 if not admin else 400, "Unable to authenticate or complete this account operation.")
    return response.json() if response.content else {}
