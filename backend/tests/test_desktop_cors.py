from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.sessions import session_key
from app.models.session import AuthSession
from tests.utils import create_user


TAURI_ORIGIN = "https://tauri.localhost"
WEB_ORIGIN = "https://b2-b-crm.vercel.app"


def use_local_legacy_auth(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "legacy")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "TENANT_ISOLATION_ENABLED", False)


def bypass_tenant_feature_gate_for_auth_probe(monkeypatch):
    # This regression isolates session-cookie validation; SaaS authorization has its own suite.
    from app.api import deps
    from app.services import subscriptions

    class AuthProbePrincipal:
        def __init__(self, user):
            self.user = user
            self.organization_id = 1
            self.organization_role = "owner"

        def __getattr__(self, name):
            return getattr(self.user, name)

    monkeypatch.setattr(deps, "resolve_tenant", lambda db, user, request: AuthProbePrincipal(user))
    monkeypatch.setattr(subscriptions, "request_feature", lambda *args, **kwargs: None)


def test_tauri_cors_preflight_allows_only_explicit_credentialed_origin(client):
    response = client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": TAURI_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == TAURI_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "GET" in response.headers["access-control-allow-methods"]
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


def test_tauri_credentialed_session_login_me_and_logout_use_secure_none_cookie(client, db, monkeypatch):
    use_local_legacy_auth(monkeypatch)
    bypass_tenant_feature_gate_for_auth_probe(monkeypatch)
    monkeypatch.setattr(settings, "COOKIE_SECURE", False)
    user = create_user(db, password="DesktopTestPassword!")
    login = client.post(
        "/api/v1/auth/login",
        data={"username": user.email, "password": "DesktopTestPassword!"},
        headers={"Origin": TAURI_ORIGIN},
    )
    assert login.status_code == 200
    assert login.headers["access-control-allow-origin"] == TAURI_ORIGIN
    assert login.headers["access-control-allow-credentials"] == "true"
    cookie = login.cookies.get(settings.SESSION_COOKIE_NAME)
    assert cookie
    assert all(part in login.headers["set-cookie"].lower() for part in ["httponly", "secure", "samesite=none", "path=/api"])

    me = client.get(
        "/api/v1/auth/me",
        headers={"Origin": TAURI_ORIGIN, "Cookie": f"{settings.SESSION_COOKIE_NAME}={cookie}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == user.email
    assert me.headers["access-control-allow-origin"] == TAURI_ORIGIN
    assert me.headers["access-control-allow-credentials"] == "true"

    logout = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": TAURI_ORIGIN, "Cookie": f"{settings.SESSION_COOKIE_NAME}={cookie}"},
    )
    assert logout.status_code == 204
    assert "samesite=none" in logout.headers["set-cookie"].lower()
    expired = client.get(
        "/api/v1/auth/me",
        headers={"Origin": TAURI_ORIGIN, "Cookie": f"{settings.SESSION_COOKIE_NAME}={cookie}"},
    )
    assert expired.status_code == 401


def test_tauri_session_expiry_is_enforced(client, db, monkeypatch):
    use_local_legacy_auth(monkeypatch)
    bypass_tenant_feature_gate_for_auth_probe(monkeypatch)
    user = create_user(db, password="DesktopTestPassword!")
    login = client.post(
        "/api/v1/auth/login",
        data={"username": user.email, "password": "DesktopTestPassword!"},
        headers={"Origin": TAURI_ORIGIN},
    )
    cookie = login.cookies.get(settings.SESSION_COOKIE_NAME)
    assert cookie
    session = db.get(AuthSession, session_key(cookie))
    assert session
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    response = client.get(
        "/api/v1/auth/me",
        headers={"Origin": TAURI_ORIGIN, "Cookie": f"{settings.SESSION_COOKIE_NAME}={cookie}"},
    )
    assert response.status_code == 401


def test_web_session_cookie_remains_lax(client, db, monkeypatch):
    use_local_legacy_auth(monkeypatch)
    user = create_user(db, password="WebTestPassword!")
    response = client.post(
        "/api/v1/auth/login",
        data={"username": user.email, "password": "WebTestPassword!"},
        headers={"Origin": WEB_ORIGIN},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == WEB_ORIGIN
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    assert "samesite=none" not in response.headers["set-cookie"].lower()


def test_tauri_cookie_writes_still_reject_unapproved_origin(client, db, monkeypatch):
    use_local_legacy_auth(monkeypatch)
    monkeypatch.setattr(settings, "COOKIE_SECURE", False)
    user = create_user(db, password="DesktopTestPassword!")
    login = client.post(
        "/api/v1/auth/login",
        data={"username": user.email, "password": "DesktopTestPassword!"},
        headers={"Origin": TAURI_ORIGIN},
    )
    cookie = login.cookies.get(settings.SESSION_COOKIE_NAME)
    response = client.post(
        "/api/v1/companies",
        json={"name": "Should not be created"},
        headers={"Origin": "https://attacker.example", "Cookie": f"{settings.SESSION_COOKIE_NAME}={cookie}"},
    )
    assert response.status_code == 403
