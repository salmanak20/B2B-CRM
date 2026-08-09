from datetime import datetime
from decimal import Decimal

from app.models.activity import Activity
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.lead import Lead
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.models.task import Task
from tests.utils import (
    auth_headers,
    create_activity,
    create_company,
    create_contact,
    create_deal,
    create_lead,
    create_task,
    create_user,
)


def dec(value) -> Decimal:
    return Decimal(str(value))


def get_seeded_pipeline_stages(db):
    pipeline = db.query(Pipeline).filter(Pipeline.is_default.is_(True)).first()
    open_stage = (
        db.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == pipeline.id, PipelineStage.is_closed.is_(False))
        .order_by(PipelineStage.order)
        .first()
    )
    won_stage = db.query(PipelineStage).filter(PipelineStage.pipeline_id == pipeline.id, PipelineStage.is_won.is_(True)).first()
    lost_stage = db.query(PipelineStage).filter(PipelineStage.pipeline_id == pipeline.id, PipelineStage.is_lost.is_(True)).first()
    return (
        {"id": pipeline.id, "name": pipeline.name},
        {"id": open_stage.id, "probability": open_stage.probability},
        {"id": won_stage.id, "probability": won_stage.probability},
        {"id": lost_stage.id, "probability": lost_stage.probability},
    )


def set_created_at(db, model, record_id: int, value: datetime):
    record = db.get(model, record_id)
    record.created_at = value
    db.add(record)
    db.commit()
    return record


def make_dashboard_dataset(client, db, headers, prefix: str, stamp: datetime, pipeline_data=None):
    if pipeline_data is None:
        pipeline, open_stage, won_stage, lost_stage = get_seeded_pipeline_stages(db)
    else:
        pipeline, open_stage, won_stage, lost_stage = pipeline_data
    company = create_company(client, headers, name=f"{prefix} Company")
    contact = create_contact(client, headers, company["id"])
    leads = [
        create_lead(client, headers, title=f"{prefix} New", status="new", source="website"),
        create_lead(client, headers, title=f"{prefix} Qualified", status="qualified", source="referral"),
        create_lead(client, headers, title=f"{prefix} Converted", status="converted", source="website"),
        create_lead(client, headers, title=f"{prefix} Lost", status="lost", source="email"),
    ]
    open_deal = create_deal(client, headers, pipeline["id"], open_stage["id"], value=10000)
    won_deal = create_deal(client, headers, pipeline["id"], won_stage["id"], value=20000)
    lost_deal = create_deal(client, headers, pipeline["id"], lost_stage["id"], value=5000)
    pending_task = create_task(client, headers, title=f"{prefix} Pending", priority="high", due_date="2027-01-01T09:00:00")
    overdue_task = create_task(client, headers, title=f"{prefix} Overdue", priority="urgent", due_date="2026-01-01T09:00:00")
    completed_task = create_task(client, headers, title=f"{prefix} Completed", priority="low", status="completed")
    activity = create_activity(client, headers, type="meeting", subject=f"{prefix} Meeting", occurred_at=stamp.isoformat())

    for model, record_id in [
        (Company, company["id"]),
        (Contact, contact["id"]),
        (Deal, open_deal["id"]),
        (Deal, won_deal["id"]),
        (Deal, lost_deal["id"]),
        (Task, pending_task["id"]),
        (Task, overdue_task["id"]),
        (Task, completed_task["id"]),
        (Activity, activity["id"]),
    ]:
        set_created_at(db, model, record_id, stamp)
    for lead in leads:
        set_created_at(db, Lead, lead["id"], stamp)

    won = db.get(Deal, won_deal["id"])
    won.updated_at = stamp
    completed = db.get(Task, completed_task["id"])
    completed.completed_at = stamp
    db.commit()
    return {
        "pipeline": pipeline,
        "open_stage": open_stage,
        "won_stage": won_stage,
        "lost_stage": lost_stage,
        "open_deal": open_deal,
        "won_deal": won_deal,
        "lost_deal": lost_deal,
    }


def test_dashboard_summary(client, db):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    make_dashboard_dataset(client, db, headers, "Summary", datetime(2031, 1, 15, 12, 0, 0))

    response = client.get("/api/v1/dashboard/summary?start_date=2031-01-01&end_date=2031-01-31", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_companies"] == 1
    assert body["total_contacts"] == 1
    assert body["total_leads"] == 4
    assert body["new_leads"] == 1
    assert body["converted_leads"] == 1
    assert body["total_deals"] == 3
    assert body["open_deals"] == 1
    assert body["won_deals"] == 1
    assert body["lost_deals"] == 1
    assert dec(body["total_pipeline_value"]) == Decimal("35000.00")
    assert dec(body["open_pipeline_value"]) == Decimal("10000.00")
    assert dec(body["won_revenue"]) == Decimal("20000.00")
    assert body["total_tasks"] == 3
    assert body["pending_tasks"] == 2
    assert body["completed_tasks"] == 1
    assert body["overdue_tasks"] == 1


def test_sales_performance(client, db):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    make_dashboard_dataset(client, db, headers, "Sales", datetime(2032, 1, 15, 12, 0, 0))

    response = client.get("/api/v1/dashboard/sales-performance?start_date=2032-01-01&end_date=2032-01-31", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_deals"] == 3
    assert body["won_deals"] == 1
    assert body["lost_deals"] == 1
    assert body["open_deals"] == 1
    assert dec(body["total_deal_value"]) == Decimal("35000.00")
    assert dec(body["won_revenue"]) == Decimal("20000.00")
    assert dec(body["average_deal_value"]) == Decimal("11666.67")
    assert dec(body["win_rate"]) == Decimal("33.33")
    assert dec(body["loss_rate"]) == Decimal("33.33")


def test_lead_analytics(client, db):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    make_dashboard_dataset(client, db, headers, "Leads", datetime(2033, 1, 15, 12, 0, 0))

    response = client.get("/api/v1/dashboard/lead-analytics?start_date=2033-01-01&end_date=2033-01-31", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_leads"] == 4
    assert body["new_leads"] == 1
    assert body["qualified_leads"] == 1
    assert body["converted_leads"] == 1
    assert body["lost_leads"] == 1
    assert dec(body["conversion_rate"]) == Decimal("25.00")
    assert {"status": "converted", "count": 1} in body["by_status"]
    assert {"source": "website", "count": 2} in body["by_source"]


def test_pipeline_analytics(client, db):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    data = make_dashboard_dataset(client, db, headers, "Pipeline", datetime(2034, 1, 15, 12, 0, 0))

    response = client.get("/api/v1/dashboard/pipeline-analytics?start_date=2034-01-01&end_date=2034-01-31", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["open_deals"] == 1
    assert dec(body["total_pipeline_value"]) == Decimal("10000.00")
    assert dec(body["weighted_pipeline_value"]) == Decimal("1000.00")
    assert dec(body["won_revenue"]) == Decimal("20000.00")
    assert dec(body["lost_value"]) == Decimal("5000.00")
    assert body["value_by_pipeline"][0]["pipeline_id"] == data["pipeline"]["id"]
    assert body["value_by_stage"][0]["stage_id"] == data["open_stage"]["id"]
    assert body["deal_count_by_stage"][0]["deal_count"] == 1


def test_revenue_trend(client, db):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    make_dashboard_dataset(client, db, headers, "Revenue January", datetime(2035, 1, 10, 12, 0, 0))
    make_dashboard_dataset(client, db, headers, "Revenue February", datetime(2035, 2, 10, 12, 0, 0))

    response = client.get("/api/v1/dashboard/revenue-trend?period=monthly&start_date=2035-01-01&end_date=2035-02-28", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "monthly"
    assert body["data"] == [
        {"period": "2035-01", "revenue": "20000.00", "deals_won": 1},
        {"period": "2035-02", "revenue": "20000.00", "deals_won": 1},
    ]


def test_activity_summary(client, db):
    headers = auth_headers(client, "admin@example.com", "adminpass")
    make_dashboard_dataset(client, db, headers, "Activity", datetime(2036, 1, 15, 12, 0, 0))

    response = client.get("/api/v1/dashboard/activity-summary?start_date=2036-01-01&end_date=2036-01-31", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_tasks"] == 3
    assert body["pending_tasks"] == 2
    assert body["in_progress_tasks"] == 0
    assert body["completed_tasks"] == 1
    assert body["overdue_tasks"] == 1
    assert {"priority": "urgent", "count": 1} in body["tasks_by_priority"]
    assert {"type": "meeting", "count": 1} in body["activities_by_type"]
    assert body["activities_completed"] == 1
    assert body["upcoming_tasks"] == 1


def test_team_performance(client, db):
    admin_headers = auth_headers(client, "admin@example.com", "adminpass")
    rep = create_user(db, "sales_rep")
    rep_headers = auth_headers(client, rep.email)
    make_dashboard_dataset(client, db, rep_headers, "Team", datetime(2037, 1, 15, 12, 0, 0))

    response = client.get("/api/v1/dashboard/team-performance?start_date=2037-01-01&end_date=2037-01-31", headers=admin_headers)
    assert response.status_code == 200
    users = {user["user_id"]: user for user in response.json()["users"]}
    assert rep.id in users
    assert users[rep.id]["leads"] == 4
    assert users[rep.id]["deals"] == 3
    assert users[rep.id]["open_deals"] == 1
    assert users[rep.id]["won_deals"] == 1
    assert users[rep.id]["lost_deals"] == 1
    assert dec(users[rep.id]["pipeline_value"]) == Decimal("10000.00")
    assert dec(users[rep.id]["won_revenue"]) == Decimal("20000.00")
    assert dec(users[rep.id]["win_rate"]) == Decimal("33.33")
    assert users[rep.id]["completed_tasks"] == 1


def test_dashboard_date_filtering_invalid_range_and_empty_results(client):
    headers = auth_headers(client, "admin@example.com", "adminpass")

    response = client.get("/api/v1/dashboard/summary?start_date=2040-02-01&end_date=2040-01-01", headers=headers)
    assert response.status_code == 422

    response = client.get("/api/v1/dashboard/lead-analytics?start_date=2100-01-01&end_date=2100-01-31", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_leads"] == 0
    assert body["conversion_rate"] == "0"
    assert body["by_status"] == []
    assert body["by_source"] == []


def test_dashboard_rbac_and_sales_rep_data_isolation(client, db):
    admin_headers = auth_headers(client, "admin@example.com", "adminpass")
    manager = create_user(db, "sales_manager")
    viewer = create_user(db, "viewer")
    rep_a = create_user(db, "sales_rep")
    rep_b = create_user(db, "sales_rep")
    manager_headers = auth_headers(client, manager.email)
    viewer_headers = auth_headers(client, viewer.email)
    rep_a_headers = auth_headers(client, rep_a.email)
    rep_b_headers = auth_headers(client, rep_b.email)

    make_dashboard_dataset(client, db, rep_a_headers, "Rep A", datetime(2038, 1, 15, 12, 0, 0))
    make_dashboard_dataset(client, db, rep_b_headers, "Rep B", datetime(2038, 1, 15, 12, 0, 0))

    response = client.get("/api/v1/dashboard/summary?start_date=2038-01-01&end_date=2038-01-31", headers=rep_a_headers)
    assert response.status_code == 200
    assert response.json()["total_deals"] == 3

    response = client.get("/api/v1/dashboard/team-performance?start_date=2038-01-01&end_date=2038-01-31", headers=rep_a_headers)
    assert response.status_code == 200
    assert [user["user_id"] for user in response.json()["users"]] == [rep_a.id]

    for headers in [admin_headers, manager_headers, viewer_headers]:
        response = client.get("/api/v1/dashboard/summary?start_date=2038-01-01&end_date=2038-01-31", headers=headers)
        assert response.status_code == 200
        assert response.json()["total_deals"] == 6

    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 401
