from fastapi.testclient import TestClient
from tests.utils import auth_headers, create_user

def test_export_companies(client: TestClient, db):
    admin = create_user(db, "admin")
    headers = auth_headers(client, admin.email)

    r = client.get("/api/v1/exports/companies", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/csv; charset=utf-8"

def test_export_contacts(client: TestClient, db):
    admin = create_user(db, "admin")
    headers = auth_headers(client, admin.email)

    r = client.get("/api/v1/exports/contacts", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/csv; charset=utf-8"

def test_export_leads(client: TestClient, db):
    admin = create_user(db, "admin")
    headers = auth_headers(client, admin.email)

    r = client.get("/api/v1/exports/leads", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/csv; charset=utf-8"

def test_export_deals(client: TestClient, db):
    admin = create_user(db, "admin")
    headers = auth_headers(client, admin.email)

    r = client.get("/api/v1/exports/deals", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/csv; charset=utf-8"

def test_export_tasks(client: TestClient, db):
    admin = create_user(db, "admin")
    headers = auth_headers(client, admin.email)

    r = client.get("/api/v1/exports/tasks", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/csv; charset=utf-8"
