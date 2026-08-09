from fastapi.testclient import TestClient
from tests.utils import auth_headers, create_user

def test_reports_sales(client: TestClient, db):
    admin = create_user(db, "admin")
    headers = auth_headers(client, admin.email)
    
    r = client.get("/api/v1/reports/sales", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "total_deals" in data
    assert "total_value" in data

def test_reports_leads(client: TestClient, db):
    admin = create_user(db, "admin")
    headers = auth_headers(client, admin.email)

    r = client.get("/api/v1/reports/leads", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "total_leads" in data
    
def test_reports_deals(client: TestClient, db):
    admin = create_user(db, "admin")
    headers = auth_headers(client, admin.email)

    r = client.get("/api/v1/reports/deals", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "total_deals" in data
    
def test_reports_tasks(client: TestClient, db):
    admin = create_user(db, "admin")
    headers = auth_headers(client, admin.email)

    r = client.get("/api/v1/reports/tasks", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "total_tasks" in data
    
def test_reports_team(client: TestClient, db):
    admin = create_user(db, "admin")
    headers = auth_headers(client, admin.email)

    r = client.get("/api/v1/reports/team", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "team_performance" in data
