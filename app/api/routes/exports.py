from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from typing import Optional, Any
import csv
import io
from sqlalchemy.orm import Session
from datetime import datetime

from app.api.deps import SessionDep, CurrentActiveUser, require_permission
from app.models.company import Company
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.deal import Deal
from app.models.task import Task
from app.api.ownership import READ_ALL_CRM_ROLES

router = APIRouter()

def get_rbac_filter(query, model, current_user):
    if current_user.role.name not in READ_ALL_CRM_ROLES:
        if hasattr(model, 'owner_id'):
            return query.filter(model.owner_id == current_user.id)
        elif hasattr(model, 'assigned_to_id'):
            from sqlalchemy import or_
            return query.filter(or_(model.owner_id == current_user.id, model.assigned_to_id == current_user.id))
    return query

def generate_csv(data: list, fieldnames: list) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in data:
        writer.writerow(row)
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=export.csv"}
    )

@router.get("/companies", dependencies=[Depends(require_permission("exports.read"))])
def export_companies(
    db: SessionDep,
    current_user: CurrentActiveUser,
):
    q = db.query(Company)
    q = get_rbac_filter(q, Company, current_user)
    companies = q.all()
    
    data = [
        {"id": c.id, "name": c.name, "industry": c.industry, "website": c.website, "created_at": c.created_at}
        for c in companies
    ]
    if not data:
        return generate_csv([], ["id", "name", "industry", "website", "created_at"])
    return generate_csv(data, list(data[0].keys()))

@router.get("/contacts", dependencies=[Depends(require_permission("exports.read"))])
def export_contacts(
    db: SessionDep,
    current_user: CurrentActiveUser,
):
    q = db.query(Contact)
    q = get_rbac_filter(q, Contact, current_user)
    contacts = q.all()
    
    data = [
        {"id": c.id, "first_name": c.first_name, "last_name": c.last_name, "email": c.email, "phone": c.phone, "company_id": c.company_id}
        for c in contacts
    ]
    if not data:
        return generate_csv([], ["id", "first_name", "last_name", "email", "phone", "company_id"])
    return generate_csv(data, list(data[0].keys()))

@router.get("/leads", dependencies=[Depends(require_permission("exports.read"))])
def export_leads(
    db: SessionDep,
    current_user: CurrentActiveUser,
):
    q = db.query(Lead)
    q = get_rbac_filter(q, Lead, current_user)
    leads = q.all()
    
    data = [
        {"id": l.id, "title": l.title, "name": l.name, "source": l.source, "status": l.status, "estimated_value": l.estimated_value}
        for l in leads
    ]
    if not data:
        return generate_csv([], ["id", "title", "name", "source", "status", "estimated_value"])
    return generate_csv(data, list(data[0].keys()))

@router.get("/deals", dependencies=[Depends(require_permission("exports.read"))])
def export_deals(
    db: SessionDep,
    current_user: CurrentActiveUser,
):
    q = db.query(Deal)
    q = get_rbac_filter(q, Deal, current_user)
    deals = q.all()
    
    data = [
        {"id": d.id, "title": d.title, "value": d.value, "stage_id": d.stage_id, "expected_close_date": d.expected_close_date}
        for d in deals
    ]
    if not data:
        return generate_csv([], ["id", "title", "value", "stage_id", "expected_close_date"])
    return generate_csv(data, list(data[0].keys()))

@router.get("/tasks", dependencies=[Depends(require_permission("exports.read"))])
def export_tasks(
    db: SessionDep,
    current_user: CurrentActiveUser,
):
    q = db.query(Task)
    q = get_rbac_filter(q, Task, current_user)
    tasks = q.all()
    
    data = [
        {"id": t.id, "title": t.title, "status": t.status, "due_date": t.due_date, "assigned_to_id": t.assigned_to_id}
        for t in tasks
    ]
    if not data:
        return generate_csv([], ["id", "title", "status", "due_date", "assigned_to_id"])
    return generate_csv(data, list(data[0].keys()))
