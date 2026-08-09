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


def make_crm_graph(client, headers, prefix="Task"):
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


def test_task_crud_search_filter_pagination_status_and_assignment(client, db):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    assignee = create_user(db, "sales_rep")
    company, contact, lead, deal = make_crm_graph(client, headers, "Task CRUD")

    task = create_task(
        client,
        headers,
        title="Send proposal package",
        priority="high",
        assigned_to_id=assignee.id,
        company_id=company["id"],
        contact_id=contact["id"],
        lead_id=lead["id"],
        deal_id=deal["id"],
        due_date="2026-08-10T09:30:00",
    )
    assert task["status"] == "pending"
    assert task["completed_at"] is None
    assert task["assigned_to_id"] == assignee.id

    response = client.get(f"/api/v1/tasks/{task['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Send proposal package"

    response = client.get(
        f"/api/v1/tasks?search=proposal&priority=high&status=pending&assigned_to_id={assignee.id}"
        f"&company_id={company['id']}&contact_id={contact['id']}&lead_id={lead['id']}&deal_id={deal['id']}"
        "&due_after=2026-08-01&due_before=2026-08-20&page=1&page_size=1",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(item["id"] == task["id"] for item in body["items"])

    response = client.put(
        f"/api/v1/tasks/{task['id']}",
        headers=headers,
        json={"description": "Include pricing options", "priority": "urgent", "status": "in_progress"},
    )
    assert response.status_code == 200
    assert response.json()["priority"] == "urgent"
    assert response.json()["completed_at"] is None

    response = client.patch(f"/api/v1/tasks/{task['id']}/status", headers=headers, json={"status": "completed"})
    assert response.status_code == 200
    assert response.json()["completed_at"] is not None

    response = client.patch(f"/api/v1/tasks/{task['id']}/status", headers=headers, json={"status": "pending"})
    assert response.status_code == 200
    assert response.json()["completed_at"] is None

    response = client.patch(f"/api/v1/tasks/{task['id']}/assignee", headers=headers, json={"assigned_to_id": None})
    assert response.status_code == 200
    assert response.json()["assigned_to_id"] is None

    response = client.delete(f"/api/v1/tasks/{task['id']}", headers=headers)
    assert response.status_code == 200


def test_task_validation_errors(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    company_a, contact_a, lead_a, deal_a = make_crm_graph(client, headers, "Task Valid A")
    company_b, contact_b, _, _ = make_crm_graph(client, headers, "Task Valid B")

    response = client.post("/api/v1/tasks", headers=headers, json={"title": "Bad", "priority": "impossible"})
    assert response.status_code == 422
    response = client.post("/api/v1/tasks", headers=headers, json={"title": "Bad", "status": "done"})
    assert response.status_code == 422

    for field in ["company_id", "contact_id", "lead_id", "deal_id"]:
        response = client.post("/api/v1/tasks", headers=headers, json={"title": "Bad", field: 999999})
        assert response.status_code == 400

    response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={"title": "Bad relationship", "company_id": company_b["id"], "contact_id": contact_a["id"]},
    )
    assert response.status_code == 400

    response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={"title": "Bad deal contact", "deal_id": deal_a["id"], "contact_id": contact_b["id"]},
    )
    assert response.status_code == 400

    response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={"title": "Bad lead company", "company_id": company_b["id"], "lead_id": lead_a["id"]},
    )
    assert response.status_code == 400


def test_task_ownership_assignment_rbac_and_idor(client, db):
    admin_headers = auth_headers(client, "admin@example.com", "adminpass")
    rep_a = create_user(db, "sales_rep")
    rep_b = create_user(db, "sales_rep")
    viewer = create_user(db, "viewer")
    rep_a_headers = auth_headers(client, rep_a.email)
    rep_b_headers = auth_headers(client, rep_b.email)
    viewer_headers = auth_headers(client, viewer.email)

    task = create_task(client, rep_a_headers, title="Rep owned task")
    response = client.get(f"/api/v1/tasks/{task['id']}", headers=rep_b_headers)
    assert response.status_code == 403
    response = client.put(f"/api/v1/tasks/{task['id']}", headers=rep_b_headers, json={"title": "Hijack"})
    assert response.status_code == 403
    response = client.patch(f"/api/v1/tasks/{task['id']}/status", headers=rep_b_headers, json={"status": "completed"})
    assert response.status_code == 403
    response = client.patch(f"/api/v1/tasks/{task['id']}/assignee", headers=rep_b_headers, json={"assigned_to_id": rep_b.id})
    assert response.status_code == 403
    response = client.delete(f"/api/v1/tasks/{task['id']}", headers=rep_b_headers)
    assert response.status_code == 403

    response = client.post("/api/v1/tasks", headers=rep_a_headers, json={"title": "Spoof", "owner_id": rep_b.id})
    assert response.status_code == 403
    response = client.post("/api/v1/tasks", headers=rep_a_headers, json={"title": "Assign other", "assigned_to_id": rep_b.id})
    assert response.status_code == 403

    assigned = create_task(client, admin_headers, title="Assigned to rep", assigned_to_id=rep_b.id)
    response = client.get(f"/api/v1/tasks/{assigned['id']}", headers=rep_b_headers)
    assert response.status_code == 200
    response = client.patch(f"/api/v1/tasks/{assigned['id']}/status", headers=rep_b_headers, json={"status": "completed"})
    assert response.status_code == 200

    response = client.get(f"/api/v1/tasks/{task['id']}", headers=viewer_headers)
    assert response.status_code == 200
    response = client.post("/api/v1/tasks", headers=viewer_headers, json={"title": "Viewer task"})
    assert response.status_code == 403
    response = client.get(f"/api/v1/tasks/{task['id']}")
    assert response.status_code == 401
