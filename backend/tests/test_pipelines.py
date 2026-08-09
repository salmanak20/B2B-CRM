from tests.utils import auth_headers, create_deal, create_pipeline, create_pipeline_stage, create_user


def test_pipeline_crud_search_filter_and_pagination(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    pipeline = create_pipeline(client, headers, name="Enterprise Sales Process")

    response = client.get(f"/api/v1/pipelines/{pipeline['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Enterprise Sales Process"

    response = client.get("/api/v1/pipelines?search=Enterprise&page=1&page_size=1", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1
    assert response.json()["page_size"] == 1

    response = client.get("/api/v1/pipelines?is_active=true", headers=headers)
    assert response.status_code == 200
    assert any(item["id"] == pipeline["id"] for item in response.json()["items"])

    response = client.put(f"/api/v1/pipelines/{pipeline['id']}", headers=headers, json={"description": "Updated"})
    assert response.status_code == 200
    assert response.json()["description"] == "Updated"

    response = client.delete(f"/api/v1/pipelines/{pipeline['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_pipeline_duplicate_and_rbac(client, db):
    admin_headers = auth_headers(client, "admin@example.com", "adminpass")
    create_pipeline(client, admin_headers, name="Duplicate Pipeline")
    response = client.post("/api/v1/pipelines", headers=admin_headers, json={"name": "Duplicate Pipeline"})
    assert response.status_code == 409

    rep = create_user(db, "sales_rep")
    rep_headers = auth_headers(client, rep.email)
    response = client.post("/api/v1/pipelines", headers=rep_headers, json={"name": "Rep Pipeline"})
    assert response.status_code == 403

    viewer = create_user(db, "viewer")
    viewer_headers = auth_headers(client, viewer.email)
    response = client.get("/api/v1/pipelines", headers=viewer_headers)
    assert response.status_code == 200
    response = client.delete("/api/v1/pipelines/1", headers=viewer_headers)
    assert response.status_code == 403


def test_pipeline_with_dependencies_cannot_be_deleted(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    pipeline = create_pipeline(client, headers, name="Protected Pipeline")
    stage = create_pipeline_stage(client, headers, pipeline["id"], name="Only Stage", order=1)

    response = client.delete(f"/api/v1/pipelines/{pipeline['id']}", headers=headers)
    assert response.status_code == 409

    deal = create_deal(client, headers, pipeline["id"], stage["id"])
    response = client.delete(f"/api/v1/pipeline-stages/{stage['id']}", headers=headers)
    assert response.status_code == 409
    assert deal["pipeline_id"] == pipeline["id"]
