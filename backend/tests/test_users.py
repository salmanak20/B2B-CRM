import pytest

def get_token(client, email, password):
    response = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    return response.json()["access_token"]

def test_users_me(client):
    # Register and login
    client.post("/api/v1/auth/register", json={"name": "Me", "email": "me@example.com", "password": "pass"})
    token = get_token(client, "me@example.com", "pass")
    
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"

def test_users_me_unauthorized(client):
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401

def test_admin_get_users(client):
    # Admin was seeded in conftest
    token = get_token(client, "admin@example.com", "adminpass")
    response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert len(response.json()) >= 1

def test_non_admin_get_users(client):
    client.post("/api/v1/auth/register", json={"name": "Non Admin", "email": "nonadmin@example.com", "password": "pass"})
    token = get_token(client, "nonadmin@example.com", "pass")
    
    response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
