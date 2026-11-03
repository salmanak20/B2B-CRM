from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.core.sessions import decrypt, session_key
from app.models.session import AuthSession
from tests.utils import create_user


TAURI_ORIGIN = "https://tauri.localhost"
WEB_ORIGIN = "https://b2-b-crm.vercel.app"


def test_desktop_allowlist_is_fixed_to_tauri_origin():
    with pytest.raises(ValidationError, match="Desktop app origin must be exactly"):
        Settings(
            DATABASE_URL="sqlite://",
            JWT_SECRET_KEY="test-only-secret-that-is-long-enough",
            DESKTOP_APP_ORIGINS=["https://attacker.example"],
        )


def test_desktop_preflight_is_credentialed_and_rejects_other_origins(client):
    for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
        response = client.options(
            "/api/v1/auth/me",
            headers={
                "Origin": TAURI_ORIGIN,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == TAURI_ORIGIN
        assert response.headers["access-control-allow-origin"] != "*"
        assert response.headers["access-control-allow-credentials"] == "true"
        assert method in response.headers["access-control-allow-methods"]
        assert "content-type" in response.headers["access-control-allow-headers"].lower()

    rejected = client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers


def test_desktop_login_session_persistence_expiry_and_logout(client, db, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "legacy")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "COOKIE_SECURE", False)
    user = create_user(db, password="DesktopTestPassword!")
    login = client.post(
        "/api/v1/auth/login?remember=true",
        data={"username": user.email, "password": "DesktopTestPassword!"},
        headers={"Origin": TAURI_ORIGIN},
    )
    assert login.status_code == 200
    assert login.headers["access-control-allow-origin"] == TAURI_ORIGIN
    assert login.headers["access-control-allow-credentials"] == "true"
    cookie = login.cookies.get(settings.SESSION_COOKIE_NAME)
    assert cookie
    set_cookie = login.headers["set-cookie"].lower()
    assert all(part in set_cookie for part in ["httponly", "secure", "samesite=none", "path=/api"])
    assert f"max-age={settings.REMEMBER_DAYS * 86400}" in set_cookie

    headers = {"Origin": TAURI_ORIGIN, "Cookie": f"{settings.SESSION_COOKIE_NAME}={cookie}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["email"] == user.email

    session = db.get(AuthSession, session_key(cookie))
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        data={"username": user.email, "password": "DesktopTestPassword!"},
        headers={"Origin": TAURI_ORIGIN},
    )
    cookie = login.cookies.get(settings.SESSION_COOKIE_NAME)
    headers = {"Origin": TAURI_ORIGIN, "Cookie": f"{settings.SESSION_COOKIE_NAME}={cookie}"}
    logout = client.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 204
    assert "samesite=none" in logout.headers["set-cookie"].lower()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_desktop_session_refreshes_provider_tokens(client, db, monkeypatch):
    import app.api.routes.auth as auth
    import app.core.sessions as sessions

    monkeypatch.setattr(settings, "AUTH_PROVIDER", "supabase")
    user = create_user(db, password="DesktopTestPassword!")
    user.auth_user_id = str(uuid4())
    db.commit()
    identity = {"id": user.auth_user_id, "email": user.email, "email_confirmed_at": "2026-10-15T00:00:00Z"}
    calls = []

    def provider(method, path, data=None, **kwargs):
        calls.append((method, path, data))
        if path == "/token?grant_type=password":
            return {"access_token": "access-before", "refresh_token": "refresh-before", "expires_in": 3600, "user": identity}
        if path == "/token?grant_type=refresh_token":
            assert data["refresh_token"] == "refresh-before"
            return {"access_token": "access-after", "refresh_token": "refresh-after", "expires_in": 3600}
        if path == "/user":
            return identity
        raise AssertionError(f"Unexpected provider call: {method} {path}")

    monkeypatch.setattr(auth, "auth_request", provider)
    monkeypatch.setattr(sessions, "auth_request", provider)
    login = client.post(
        "/api/v1/auth/login",
        data={"username": user.email, "password": "provider-handled"},
        headers={"Origin": TAURI_ORIGIN},
    )
    assert login.status_code == 200
    cookie = login.cookies.get(settings.SESSION_COOKIE_NAME)
    row = db.get(AuthSession, session_key(cookie))
    row.access_expires_at = datetime.now(timezone.utc) + timedelta(seconds=5)
    db.commit()

    headers = {"Origin": TAURI_ORIGIN, "Cookie": f"{settings.SESSION_COOKIE_NAME}={cookie}"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["email"] == user.email
    assert decrypt(row.access_token) == "access-after"
    assert any(path == "/token?grant_type=refresh_token" for _, path, _ in calls)
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200


def test_unapproved_origin_cannot_write_and_missing_origin_with_session_is_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    cookie = f"{settings.SESSION_COOKIE_NAME}=invalid"
    blocked = client.post(
        "/api/v1/companies",
        json={"name": "Must not be created"},
        headers={"Origin": "https://attacker.example", "Cookie": cookie},
    )
    assert blocked.status_code == 403
    missing = client.post(
        "/api/v1/companies",
        json={"name": "Must not be created"},
        headers={"Cookie": cookie},
    )
    assert missing.status_code == 403


def test_web_login_keeps_secure_lax_session_cookie(client, db, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "legacy")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "COOKIE_SECURE", True)
    user = create_user(db, password="WebTestPassword!")
    response = client.post(
        "/api/v1/auth/login",
        data={"username": user.email, "password": "WebTestPassword!"},
        headers={"Origin": WEB_ORIGIN},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == WEB_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    cookie = response.headers["set-cookie"].lower()
    assert all(part in cookie for part in ["samesite=lax", "secure", "httponly", "path=/api"])
    assert "samesite=none" not in cookie


def test_arbitrary_origin_is_never_reflected(client):
    response = client.get("/api/v1/health", headers={"Origin": "https://attacker.example"})
    assert "access-control-allow-origin" not in response.headers
