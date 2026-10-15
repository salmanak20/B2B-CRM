from datetime import datetime, timedelta, timezone
import jwt

from tests.utils import auth_headers, create_user
from app.core.config import settings


def test_register(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Test User", "email": "test@example.com", "password": "ValidPassword123!"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "password" not in data
    assert "password_hash" not in data

def test_register_duplicate(client):
    # Already registered above
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Test User 2", "email": "test@example.com", "password": "ValidPassword123!"}
    )
    assert response.status_code == 409

def test_login(client):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@example.com", "password": "ValidPassword123!"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_invalid(client):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401


# ── New security cases ────────────────────────────────────────────────────────

def test_login_inactive_user(client, db):
    """Deactivated users must not be able to log in."""
    user = create_user(db, "sales_rep", password="testpass")
    # Deactivate directly in DB
    user.is_active = False
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        data={"username": user.email, "password": "testpass"}
    )
    assert response.status_code == 401
    # Re-activate so the shared DB is not polluted for other tests
    user.is_active = True
    db.commit()


def test_malformed_bearer_token_rejected(client):
    """Random garbage in the Authorization header must return 401."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer totally.not.a.valid.jwt"}
    )
    assert response.status_code == 401


def test_expired_jwt_rejected(client):
    """A structurally valid JWT that is already expired must return 401."""
    expired_token = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401


def test_register_missing_required_fields(client):
    """Registration without required fields must fail with 422."""
    # Missing password
    r = client.post("/api/v1/auth/register", json={"name": "No Pass", "email": "nopass@example.com"})
    assert r.status_code == 422
    # Missing email
    r = client.post("/api/v1/auth/register", json={"name": "No Email", "password": "pass"})
    assert r.status_code == 422


def test_me_requires_auth(client):
    """/auth/me without any token must return 401."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
