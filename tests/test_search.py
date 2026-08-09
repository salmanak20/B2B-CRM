from fastapi.testclient import TestClient
from tests.utils import auth_headers, create_user

def test_global_search_empty(client: TestClient, db):
    normal_user = create_user(db, "sales_rep")
    headers = auth_headers(client, normal_user.email)
    
    r = client.get("/api/v1/search?q=a", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["companies"] == []

def test_global_search_term(client: TestClient, db):
    normal_user = create_user(db, "sales_rep")
    headers = auth_headers(client, normal_user.email)

    r = client.get("/api/v1/search?q=test", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "companies" in data
    assert "contacts" in data
    assert "leads" in data
    assert "deals" in data
    assert "tasks" in data
