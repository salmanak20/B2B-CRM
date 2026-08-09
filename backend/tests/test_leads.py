from tests.utils import auth_headers, create_company, create_contact, create_lead, create_user


def test_lead_crud_search_filter_and_pagination(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    company = create_company(client, headers, name="Lead Parent")
    contact = create_contact(client, headers, company["id"])
    lead = create_lead(
        client,
        headers,
        title="Software Expansion",
        company_id=company["id"],
        contact_id=contact["id"],
        status="qualified",
        source="referral",
    )

    response = client.get(f"/api/v1/leads/{lead['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Software Expansion"

    response = client.get("/api/v1/leads?search=software&page=1&page_size=1", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1

    response = client.get(
        f"/api/v1/leads?company_id={company['id']}&contact_id={contact['id']}&status=qualified&source=referral",
        headers=headers,
    )
    assert response.status_code == 200
    assert any(item["id"] == lead["id"] for item in response.json()["items"])

    response = client.put(
        f"/api/v1/leads/{lead['id']}",
        headers=headers,
        json={"status": "converted", "estimated_value": 50000},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "converted"
    assert response.json()["estimated_value"] == 50000

    response = client.delete(f"/api/v1/leads/{lead['id']}", headers=headers)
    assert response.status_code == 200


def test_lead_validation_errors(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    response = client.post(
        "/api/v1/leads",
        headers=headers,
        json={"title": "Bad Status", "status": "invalid_status"},
    )
    assert response.status_code == 422

    response = client.post(
        "/api/v1/leads",
        headers=headers,
        json={"title": "Bad Source", "status": "new", "source": "trade_show"},
    )
    assert response.status_code == 422

    response = client.post(
        "/api/v1/leads",
        headers=headers,
        json={"title": "Bad Company", "status": "new", "company_id": 9999},
    )
    assert response.status_code == 400

    response = client.post(
        "/api/v1/leads",
        headers=headers,
        json={"title": "Bad Contact", "status": "new", "contact_id": 9999},
    )
    assert response.status_code == 400


def test_lead_rejects_contact_company_mismatch(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    company_a = create_company(client, headers, name="Company A")
    company_b = create_company(client, headers, name="Company B")
    contact = create_contact(client, headers, company_a["id"])

    response = client.post(
        "/api/v1/leads",
        headers=headers,
        json={
            "title": "Mismatch",
            "status": "new",
            "company_id": company_b["id"],
            "contact_id": contact["id"],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Contact does not belong to the selected company"


def test_lead_relationship_chain_persists(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    company = create_company(client, headers, name="Relationship Chain Co")
    contact = create_contact(client, headers, company["id"], first_name="Rel", last_name="Contact")
    lead = create_lead(client, headers, title="Relationship Chain Lead", company_id=company["id"], contact_id=contact["id"])

    response = client.get(f"/api/v1/leads/{lead['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["company_id"] == company["id"]
    assert response.json()["contact_id"] == contact["id"]


def test_lead_ownership_and_rbac_enforced(client, db):
    rep_a = create_user(db, "sales_rep")
    rep_b = create_user(db, "sales_rep")
    viewer = create_user(db, "viewer")
    rep_a_headers = auth_headers(client, rep_a.email)
    rep_b_headers = auth_headers(client, rep_b.email)
    viewer_headers = auth_headers(client, viewer.email)

    company = create_company(client, rep_a_headers, name="Rep Lead Parent")
    contact = create_contact(client, rep_a_headers, company["id"])
    lead = create_lead(client, rep_a_headers, company_id=company["id"], contact_id=contact["id"])

    response = client.put(
        f"/api/v1/leads/{lead['id']}",
        headers=rep_b_headers,
        json={"status": "qualified"},
    )
    assert response.status_code == 403

    response = client.delete(f"/api/v1/leads/{lead['id']}", headers=rep_b_headers)
    assert response.status_code == 403

    response = client.post(
        "/api/v1/leads",
        headers=viewer_headers,
        json={"title": "Viewer Create", "status": "new"},
    )
    assert response.status_code == 403

    response = client.post(
        "/api/v1/leads",
        headers=rep_a_headers,
        json={"title": "Spoof Lead", "status": "new", "owner_id": rep_b.id},
    )
    assert response.status_code == 403
