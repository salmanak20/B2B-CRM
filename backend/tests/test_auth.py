def test_register(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Test User", "email": "test@example.com", "password": "password123"}
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
        json={"name": "Test User 2", "email": "test@example.com", "password": "password123"}
    )
    assert response.status_code == 409

def test_login(client):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@example.com", "password": "password123"}
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
