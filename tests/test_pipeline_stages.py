from tests.utils import auth_headers, create_deal, create_pipeline, create_pipeline_stage, create_user


def test_stage_crud_ordering_and_listing(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    pipeline = create_pipeline(client, headers, name="Stage Ordering Pipeline")
    later = create_pipeline_stage(client, headers, pipeline["id"], name="Later", order=2, probability=50)
    earlier = create_pipeline_stage(client, headers, pipeline["id"], name="Earlier", order=1, probability=10)

    response = client.get(f"/api/v1/pipelines/{pipeline['id']}/stages", headers=headers)
    assert response.status_code == 200
    stage_ids = [item["id"] for item in response.json()["items"]]
    assert stage_ids[:2] == [earlier["id"], later["id"]]

    response = client.get(f"/api/v1/pipeline-stages/{later['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Later"

    response = client.put(
        f"/api/v1/pipeline-stages/{later['id']}",
        headers=headers,
        json={"name": "Updated Later", "probability": 65},
    )
    assert response.status_code == 200
    assert response.json()["probability"] == 65

    response = client.delete(f"/api/v1/pipeline-stages/{earlier['id']}", headers=headers)
    assert response.status_code == 200


def test_stage_duplicate_invalid_pipeline_and_rbac(client, db):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    pipeline = create_pipeline(client, headers, name="Duplicate Stage Pipeline")
    create_pipeline_stage(client, headers, pipeline["id"], name="New", order=1)

    response = client.post(
        f"/api/v1/pipelines/{pipeline['id']}/stages",
        headers=headers,
        json={"name": "Another", "order": 1, "probability": 20},
    )
    assert response.status_code == 409

    response = client.post(
        f"/api/v1/pipelines/{pipeline['id']}/stages",
        headers=headers,
        json={"name": "New", "order": 2, "probability": 20},
    )
    assert response.status_code == 409

    response = client.post(
        "/api/v1/pipelines/999999/stages",
        headers=headers,
        json={"name": "Missing", "order": 1, "probability": 20},
    )
    assert response.status_code == 400

    rep = create_user(db, "sales_rep")
    rep_headers = auth_headers(client, rep.email)
    response = client.post(
        f"/api/v1/pipelines/{pipeline['id']}/stages",
        headers=rep_headers,
        json={"name": "Rep Stage", "order": 3},
    )
    assert response.status_code == 403


def test_stage_delete_conflict_when_deals_reference_it(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    pipeline = create_pipeline(client, headers, name="Stage Delete Conflict Pipeline")
    stage = create_pipeline_stage(client, headers, pipeline["id"], name="Active", order=1)
    create_deal(client, headers, pipeline["id"], stage["id"])

    response = client.delete(f"/api/v1/pipeline-stages/{stage['id']}", headers=headers)
    assert response.status_code == 409


def test_closed_stage_state_validation(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    pipeline = create_pipeline(client, headers, name="Closed Stage Validation")
    response = client.post(
        f"/api/v1/pipelines/{pipeline['id']}/stages",
        headers=headers,
        json={"name": "Impossible", "order": 1, "probability": 100, "is_won": True, "is_lost": True},
    )
    assert response.status_code == 422
