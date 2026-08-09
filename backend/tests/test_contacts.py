from tests.utils import auth_headers, create_company, create_contact, create_user


def test_contact_crud_search_filter_and_pagination(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    company = create_company(client, headers, name="Contact Parent")
    contact = create_contact(
        client,
        headers,
        company["id"],
        first_name="John",
        last_name="Smith",
        job_title="Procurement Lead",
    )

    response = client.get(f"/api/v1/contacts/{contact['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["first_name"] == "John"
    assert response.json()["name"] == "John Smith"

    response = client.get("/api/v1/contacts?search=Procurement&page=1&page_size=1", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1
    assert response.json()["page_size"] == 1

    response = client.get(f"/api/v1/contacts?company_id={company['id']}", headers=headers)
    assert response.status_code == 200
    assert any(item["id"] == contact["id"] for item in response.json()["items"])

    response = client.put(
        f"/api/v1/contacts/{contact['id']}",
        headers=headers,
        json={"first_name": "Jonathan", "description": "Primary buyer"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Jonathan Smith"

    response = client.delete(f"/api/v1/contacts/{contact['id']}", headers=headers)
    assert response.status_code == 200


def test_contact_invalid_company_and_email(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    response = client.post(
        "/api/v1/contacts",
        headers=headers,
        json={"first_name": "No", "last_name": "Company", "company_id": 9999},
    )
    assert response.status_code == 400

    company = create_company(client, headers, name="Bad Email Co")
    response = client.post(
        "/api/v1/contacts",
        headers=headers,
        json={"first_name": "Bad", "email": "not-an-email", "company_id": company["id"]},
    )
    assert response.status_code == 422


def test_contact_ownership_and_rbac_enforced(client, db):
    rep_a = create_user(db, "sales_rep")
    rep_b = create_user(db, "sales_rep")
    viewer = create_user(db, "viewer")
    rep_a_headers = auth_headers(client, rep_a.email)
    rep_b_headers = auth_headers(client, rep_b.email)
    viewer_headers = auth_headers(client, viewer.email)

    company = create_company(client, rep_a_headers, name="Rep Contact Parent")
    contact = create_contact(client, rep_a_headers, company["id"])

    response = client.put(
        f"/api/v1/contacts/{contact['id']}",
        headers=rep_b_headers,
        json={"first_name": "Other"},
    )
    assert response.status_code == 403

    response = client.delete(f"/api/v1/contacts/{contact['id']}", headers=rep_b_headers)
    assert response.status_code == 403

    response = client.post(
        "/api/v1/contacts",
        headers=viewer_headers,
        json={"first_name": "Read", "last_name": "Only", "company_id": company["id"]},
    )
    assert response.status_code == 403

    response = client.post(
        "/api/v1/contacts",
        headers=rep_b_headers,
        json={"first_name": "Wrong", "last_name": "Company", "company_id": company["id"]},
    )
    assert response.status_code == 403


def test_contact_owner_filter(client, db):
    rep = create_user(db, "sales_rep")
    headers = auth_headers(client, rep.email)
    company = create_company(client, headers, name="Owner Filter Contact Co")
    contact = create_contact(client, headers, company["id"])

    response = client.get(f"/api/v1/contacts?owner_id={rep.id}", headers=headers)
    assert response.status_code == 200
    assert any(item["id"] == contact["id"] for item in response.json()["items"])
