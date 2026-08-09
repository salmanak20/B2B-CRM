from tests.utils import (
    auth_headers,
    create_company,
    create_contact,
    create_deal,
    create_lead,
    create_pipeline,
    create_pipeline_stage,
    create_user,
)


def make_pipeline_with_stages(client, headers, name="Deal Pipeline"):
    pipeline = create_pipeline(client, headers, name=name)
    new_stage = create_pipeline_stage(client, headers, pipeline["id"], name="New", order=1, probability=10)
    won_stage = create_pipeline_stage(
        client,
        headers,
        pipeline["id"],
        name="Won",
        order=2,
        probability=100,
        is_closed=True,
        is_won=True,
    )
    lost_stage = create_pipeline_stage(
        client,
        headers,
        pipeline["id"],
        name="Lost",
        order=3,
        probability=0,
        is_closed=True,
        is_lost=True,
    )
    return pipeline, new_stage, won_stage, lost_stage


def test_deal_crud_search_filter_and_pagination(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    pipeline, stage, _, _ = make_pipeline_with_stages(client, headers, "CRUD Deal Pipeline")
    company = create_company(client, headers, name="Deal Company")
    contact = create_contact(client, headers, company["id"])
    lead = create_lead(client, headers, company_id=company["id"], contact_id=contact["id"])

    deal = create_deal(
        client,
        headers,
        pipeline["id"],
        stage["id"],
        title="Acme Expansion Deal",
        company_id=company["id"],
        contact_id=contact["id"],
        lead_id=lead["id"],
        expected_close_date="2026-12-31",
    )
    assert deal["status"] == "open"

    response = client.get(f"/api/v1/deals/{deal['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Acme Expansion Deal"

    response = client.get("/api/v1/deals?search=Expansion&page=1&page_size=1", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1

    response = client.get(
        f"/api/v1/deals?pipeline_id={pipeline['id']}&stage_id={stage['id']}&company_id={company['id']}&contact_id={contact['id']}&lead_id={lead['id']}&status=open",
        headers=headers,
    )
    assert response.status_code == 200
    assert any(item["id"] == deal["id"] for item in response.json()["items"])

    response = client.put(
        f"/api/v1/deals/{deal['id']}",
        headers=headers,
        json={"value": 50000, "probability": 75},
    )
    assert response.status_code == 200
    assert response.json()["value"] == "50000.00"
    assert response.json()["probability"] == 75

    response = client.delete(f"/api/v1/deals/{deal['id']}", headers=headers)
    assert response.status_code == 200


def test_deal_validation_errors(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    pipeline, stage, _, _ = make_pipeline_with_stages(client, headers, "Validation Deal Pipeline")

    bad_payload = {"title": "Bad", "pipeline_id": pipeline["id"], "stage_id": stage["id"]}
    response = client.post("/api/v1/deals", headers=headers, json={**bad_payload, "value": -1})
    assert response.status_code == 422
    response = client.post("/api/v1/deals", headers=headers, json={**bad_payload, "probability": 101})
    assert response.status_code == 422
    response = client.post("/api/v1/deals", headers=headers, json={**bad_payload, "probability": -1})
    assert response.status_code == 422

    response = client.post("/api/v1/deals", headers=headers, json={**bad_payload, "company_id": 9999})
    assert response.status_code == 400
    response = client.post("/api/v1/deals", headers=headers, json={**bad_payload, "contact_id": 9999})
    assert response.status_code == 400
    response = client.post("/api/v1/deals", headers=headers, json={**bad_payload, "lead_id": 9999})
    assert response.status_code == 400
    response = client.post("/api/v1/deals", headers=headers, json={**bad_payload, "pipeline_id": 9999})
    assert response.status_code == 400
    response = client.post("/api/v1/deals", headers=headers, json={**bad_payload, "stage_id": 9999})
    assert response.status_code == 400


def test_deal_rejects_mismatched_relationships(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    pipeline_a, stage_a, _, _ = make_pipeline_with_stages(client, headers, "Pipeline A")
    pipeline_b, stage_b, _, _ = make_pipeline_with_stages(client, headers, "Pipeline B")
    company_a = create_company(client, headers, name="Deal Company A")
    company_b = create_company(client, headers, name="Deal Company B")
    contact_a = create_contact(client, headers, company_a["id"])
    lead_a = create_lead(client, headers, company_id=company_a["id"], contact_id=contact_a["id"])

    response = client.post(
        "/api/v1/deals",
        headers=headers,
        json={"title": "Bad Stage", "pipeline_id": pipeline_a["id"], "stage_id": stage_b["id"]},
    )
    assert response.status_code == 400

    response = client.post(
        "/api/v1/deals",
        headers=headers,
        json={
            "title": "Bad Contact Company",
            "pipeline_id": pipeline_a["id"],
            "stage_id": stage_a["id"],
            "company_id": company_b["id"],
            "contact_id": contact_a["id"],
        },
    )
    assert response.status_code == 400

    response = client.post(
        "/api/v1/deals",
        headers=headers,
        json={
            "title": "Bad Lead Company",
            "pipeline_id": pipeline_a["id"],
            "stage_id": stage_a["id"],
            "company_id": company_b["id"],
            "lead_id": lead_a["id"],
        },
    )
    assert response.status_code == 400


def test_deal_stage_movement_updates_status(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    pipeline, stage, won_stage, lost_stage = make_pipeline_with_stages(client, headers, "Movement Pipeline")
    other_pipeline, other_stage, _, _ = make_pipeline_with_stages(client, headers, "Movement Other Pipeline")
    deal = create_deal(client, headers, pipeline["id"], stage["id"])

    response = client.patch(f"/api/v1/deals/{deal['id']}/stage", headers=headers, json={"stage_id": won_stage["id"]})
    assert response.status_code == 200
    assert response.json()["stage_id"] == won_stage["id"]
    assert response.json()["status"] == "won"

    response = client.patch(f"/api/v1/deals/{deal['id']}/stage", headers=headers, json={"stage_id": lost_stage["id"]})
    assert response.status_code == 200
    assert response.json()["status"] == "lost"

    response = client.patch(f"/api/v1/deals/{deal['id']}/stage", headers=headers, json={"stage_id": other_stage["id"]})
    assert response.status_code == 400
    assert other_pipeline["id"] != pipeline["id"]


def test_deal_ownership_and_rbac_enforced(client, db):
    admin_headers = auth_headers(client, "admin@example.com", "adminpass")
    pipeline, stage, _, _ = make_pipeline_with_stages(client, admin_headers, "Ownership Deal Pipeline")
    rep_a = create_user(db, "sales_rep")
    rep_b = create_user(db, "sales_rep")
    viewer = create_user(db, "viewer")
    rep_a_headers = auth_headers(client, rep_a.email)
    rep_b_headers = auth_headers(client, rep_b.email)
    viewer_headers = auth_headers(client, viewer.email)

    deal = create_deal(client, rep_a_headers, pipeline["id"], stage["id"])
    response = client.get(f"/api/v1/deals/{deal['id']}", headers=rep_b_headers)
    assert response.status_code == 403
    response = client.put(f"/api/v1/deals/{deal['id']}", headers=rep_b_headers, json={"title": "Hijack"})
    assert response.status_code == 403
    response = client.patch(f"/api/v1/deals/{deal['id']}/stage", headers=rep_b_headers, json={"stage_id": stage["id"]})
    assert response.status_code == 403

    response = client.post(
        "/api/v1/deals",
        headers=rep_a_headers,
        json={"title": "Spoofed", "pipeline_id": pipeline["id"], "stage_id": stage["id"], "owner_id": rep_b.id},
    )
    assert response.status_code == 403

    response = client.post(
        "/api/v1/deals",
        headers=viewer_headers,
        json={"title": "Viewer Deal", "pipeline_id": pipeline["id"], "stage_id": stage["id"]},
    )
    assert response.status_code == 403
    response = client.patch(f"/api/v1/deals/{deal['id']}/stage", headers=viewer_headers, json={"stage_id": stage["id"]})
    assert response.status_code == 403


def test_pipeline_board_returns_ordered_stages_and_deals(client, db):
    admin_headers = auth_headers(client, "admin@example.com", "adminpass")
    pipeline = create_pipeline(client, admin_headers, name="Board Pipeline")
    second = create_pipeline_stage(client, admin_headers, pipeline["id"], name="Second", order=2)
    first = create_pipeline_stage(client, admin_headers, pipeline["id"], name="First", order=1)
    deal = create_deal(client, admin_headers, pipeline["id"], first["id"], title="Board Deal")

    response = client.get(f"/api/v1/pipelines/{pipeline['id']}/board", headers=admin_headers)
    assert response.status_code == 200
    board = response.json()
    assert [stage["id"] for stage in board["stages"][:2]] == [first["id"], second["id"]]
    assert any(item["id"] == deal["id"] for item in board["stages"][0]["deals"])

    response = client.get(f"/api/v1/pipelines/{pipeline['id']}/board")
    assert response.status_code == 401

    rep = create_user(db, "sales_rep")
    rep_headers = auth_headers(client, rep.email)
    response = client.get(f"/api/v1/pipelines/{pipeline['id']}/board", headers=rep_headers)
    assert response.status_code == 200
    assert all(deal["owner_id"] == rep.id for stage in response.json()["stages"] for deal in stage["deals"])
