from fastapi.testclient import TestClient
from tests.utils import auth_headers, create_user

def test_get_audit_logs(client: TestClient, db):
    admin = create_user(db, "admin")
    headers = auth_headers(client, admin.email)

    r = client.get("/api/v1/audit-logs", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)

def test_get_audit_logs_forbidden(client: TestClient, db):
    normal_user = create_user(db, "sales_rep")
    headers = auth_headers(client, normal_user.email)

    r = client.get("/api/v1/audit-logs", headers=headers)
    assert r.status_code == 403
