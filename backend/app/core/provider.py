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
        # Translate only documented codes; never echo provider bodies, tokens or
        # account details. Keep privileged/admin operations generic.
        try: error_code=response.json().get('error_code')
        except (ValueError,AttributeError): error_code=None
        if not admin:
            if error_code=='invalid_credentials' and path=='/token?grant_type=password':
                raise HTTPException(401,'Incorrect email or password. Use the account registered for this environment.')
            if error_code=='session_not_found':
                raise HTTPException(401,'Your sign-in session has ended. Sign in again in this tab.')
            if path.startswith('/factors/') and path.endswith('/verify'):
                if error_code=='mfa_verification_failed':
                    raise HTTPException(422,'Authenticator code did not match. Enter a fresh code from the account paired with the latest setup QR code.')
                if error_code=='mfa_challenge_expired':
                    raise HTTPException(422,'Authenticator verification timed out. Enter a fresh code and try again.')
        raise HTTPException(401 if not admin else 400, "Unable to authenticate or complete this account operation.")
    return response.json() if response.content else {}
