from tests.utils import auth_headers, create_company, create_user


def test_company_crud_search_filter_and_pagination(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    company = create_company(
        client,
        headers,
        name="Acme Phase Three",
        industry="technology",
        city="Austin",
        country="USA",
        description="Target account",
    )

    response = client.get(f"/api/v1/companies/{company['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Acme Phase Three"
    assert response.json()["city"] == "Austin"

    response = client.get("/api/v1/companies?search=Acme Phase&page=1&page_size=1", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1
    assert response.json()["page_size"] == 1

    response = client.get("/api/v1/companies?industry=technology", headers=headers)
    assert response.status_code == 200
    assert any(item["id"] == company["id"] for item in response.json()["items"])

    response = client.put(
        f"/api/v1/companies/{company['id']}",
        headers=headers,
        json={"phone": "+1-555-0199", "description": "Updated account"},
    )
    assert response.status_code == 200
    assert response.json()["phone"] == "+1-555-0199"

    response = client.delete(f"/api/v1/companies/{company['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    response = client.get(f"/api/v1/companies/{company['id']}", headers=headers)
    assert response.status_code == 404


def test_company_duplicate_validation(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    create_company(client, headers, name="Duplicate Account")
    response = client.post(
        "/api/v1/companies",
        headers=headers,
        json={"name": "Duplicate Account"},
    )
    assert response.status_code == 409


def test_company_unauthorized_and_viewer_forbidden(client, db):
    response = client.post("/api/v1/companies", json={"name": "No Auth"})
    assert response.status_code == 401

    viewer = create_user(db, "viewer")
    headers = auth_headers(client, viewer.email)
    response = client.post("/api/v1/companies", headers=headers, json={"name": "Read Only"})
    assert response.status_code == 403


def test_sales_rep_company_ownership_enforced(client, db):
    rep_a = create_user(db, "sales_rep")
    rep_b = create_user(db, "sales_rep")
    rep_a_headers = auth_headers(client, rep_a.email)
    rep_b_headers = auth_headers(client, rep_b.email)

    company = create_company(client, rep_a_headers, name="Rep Owned Account")

    response = client.get(f"/api/v1/companies/{company['id']}", headers=rep_b_headers)
    assert response.status_code == 403

    response = client.put(
        f"/api/v1/companies/{company['id']}",
        headers=rep_b_headers,
        json={"name": "Hijacked Account"},
    )
    assert response.status_code == 403

    response = client.delete(f"/api/v1/companies/{company['id']}", headers=rep_b_headers)
    assert response.status_code == 403

    response = client.post(
        "/api/v1/companies",
        headers=rep_a_headers,
        json={"name": "Spoofed Owner", "owner_id": rep_b.id},
    )
    assert response.status_code == 403


def test_manager_can_assign_company_owner(client, db):
    manager = create_user(db, "sales_manager")
    rep = create_user(db, "sales_rep")
    headers = auth_headers(client, manager.email)

    response = client.post(
        "/api/v1/companies",
        headers=headers,
        json={"name": "Assigned Account", "owner_id": rep.id},
    )
    assert response.status_code == 200
    assert response.json()["owner_id"] == rep.id
