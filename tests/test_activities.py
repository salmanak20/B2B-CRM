from tests.utils import (
    auth_headers,
    create_activity,
    create_company,
    create_contact,
    create_deal,
    create_lead,
    create_pipeline,
    create_pipeline_stage,
    create_task,
    create_user,
)


def make_crm_graph(client, headers, prefix="Activity"):
    pipeline = create_pipeline(client, headers, name=f"{prefix} Pipeline")
    stage = create_pipeline_stage(client, headers, pipeline["id"], name=f"{prefix} Stage", order=1)
    company = create_company(client, headers, name=f"{prefix} Company")
    contact = create_contact(client, headers, company["id"])
    lead = create_lead(client, headers, company_id=company["id"], contact_id=contact["id"])
    deal = create_deal(
        client,
        headers,
        pipeline["id"],
        stage["id"],
        company_id=company["id"],
        contact_id=contact["id"],
        lead_id=lead["id"],
    )
    return company, contact, lead, deal


def test_activity_crud_search_filter_pagination_and_user_attribution(client, db):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    performer = create_user(db, "sales_rep")
    company, contact, lead, deal = make_crm_graph(client, headers, "Activity CRUD")

    activity = create_activity(
        client,
        headers,
        type="meeting",
        subject="Proposal walkthrough",
        user_id=performer.id,
        company_id=company["id"],
        contact_id=contact["id"],
        lead_id=lead["id"],
        deal_id=deal["id"],
        occurred_at="2026-08-09T10:00:00",
    )
    assert activity["user_id"] == performer.id
    assert activity["type"] == "meeting"

    response = client.get(f"/api/v1/activities/{activity['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["subject"] == "Proposal walkthrough"

    response = client.get(
        f"/api/v1/activities?search=walkthrough&type=meeting&user_id={performer.id}"
        f"&company_id={company['id']}&contact_id={contact['id']}&lead_id={lead['id']}&deal_id={deal['id']}"
        "&occurred_after=2026-08-01&occurred_before=2026-08-20&page=1&page_size=1",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(item["id"] == activity["id"] for item in body["items"])

    response = client.put(
        f"/api/v1/activities/{activity['id']}",
        headers=headers,
        json={"type": "follow_up", "subject": "Follow-up notes"},
    )
    assert response.status_code == 200
    assert response.json()["type"] == "follow_up"

    response = client.delete(f"/api/v1/activities/{activity['id']}", headers=headers)
    assert response.status_code == 200


def test_activity_validation_errors(client, db):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    rep = create_user(db, "sales_rep")
    company_a, contact_a, lead_a, deal_a = make_crm_graph(client, headers, "Activity Valid A")
    company_b, contact_b, _, _ = make_crm_graph(client, headers, "Activity Valid B")

    response = client.post("/api/v1/activities", headers=headers, json={"type": "sms", "subject": "Bad"})
    assert response.status_code == 422

    for field in ["company_id", "contact_id", "lead_id", "deal_id"]:
        response = client.post("/api/v1/activities", headers=headers, json={"type": "call", "subject": "Bad", field: 999999})
        assert response.status_code == 400

    response = client.post(
        "/api/v1/activities",
        headers=headers,
        json={"type": "call", "subject": "Bad relationship", "company_id": company_b["id"], "contact_id": contact_a["id"]},
    )
    assert response.status_code == 400

    response = client.post(
        "/api/v1/activities",
        headers=headers,
        json={"type": "call", "subject": "Bad deal contact", "deal_id": deal_a["id"], "contact_id": contact_b["id"]},
    )
    assert response.status_code == 400

    rep_headers = auth_headers(client, rep.email)
    response = client.post("/api/v1/activities", headers=rep_headers, json={"type": "call", "subject": "Spoof", "user_id": 1})
    assert response.status_code == 403
    response = client.post(
        "/api/v1/activities",
        headers=headers,
        json={"type": "call", "subject": "Bad lead company", "company_id": company_b["id"], "lead_id": lead_a["id"]},
    )
    assert response.status_code == 400


def test_activity_ownership_rbac_and_idor(client, db):
    rep_a = create_user(db, "sales_rep")
    rep_b = create_user(db, "sales_rep")
    viewer = create_user(db, "viewer")
    rep_a_headers = auth_headers(client, rep_a.email)
    rep_b_headers = auth_headers(client, rep_b.email)
    viewer_headers = auth_headers(client, viewer.email)

    activity = create_activity(client, rep_a_headers, subject="Rep activity")
    response = client.get(f"/api/v1/activities/{activity['id']}", headers=rep_b_headers)
    assert response.status_code == 403
    response = client.put(f"/api/v1/activities/{activity['id']}", headers=rep_b_headers, json={"subject": "Hijack"})
    assert response.status_code == 403
    response = client.delete(f"/api/v1/activities/{activity['id']}", headers=rep_b_headers)
    assert response.status_code == 403

    response = client.get(f"/api/v1/activities/{activity['id']}", headers=viewer_headers)
    assert response.status_code == 200
    response = client.post("/api/v1/activities", headers=viewer_headers, json={"type": "call", "subject": "Viewer activity"})
    assert response.status_code == 403
    response = client.get(f"/api/v1/activities/{activity['id']}")
    assert response.status_code == 401


def test_deal_timeline_combines_tasks_and_activities_in_order(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    _, _, _, deal = make_crm_graph(client, headers, "Timeline")
    _, _, _, other_deal = make_crm_graph(client, headers, "Timeline Other")

    activity = create_activity(
        client,
        headers,
        type="call",
        subject="Discovery call",
        deal_id=deal["id"],
        occurred_at="2026-08-09T10:00:00",
    )
    task = create_task(
        client,
        headers,
        title="Send proposal",
        deal_id=deal["id"],
        due_date="2026-08-09T14:00:00",
    )
    create_task(client, headers, title="Unrelated task", deal_id=other_deal["id"], due_date="2026-08-09T09:00:00")

    response = client.get(f"/api/v1/deals/{deal['id']}/timeline?page=1&page_size=10", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["type"] for item in body["items"]] == ["activity", "task"]
    assert body["items"][0]["id"] == activity["id"]
    assert body["items"][1]["id"] == task["id"]
    assert all(item["title"] != "Unrelated task" for item in body["items"])
