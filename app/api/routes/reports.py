from fastapi import APIRouter, Depends
from typing import Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import SessionDep, CurrentActiveUser, require_permission
from app.models.company import Company
from app.models.lead import Lead
from app.models.deal import Deal
from app.models.task import Task
from app.models.user import User
from app.api.ownership import READ_ALL_CRM_ROLES

router = APIRouter()

def apply_date_filter(query, model, start_date, end_date):
    if start_date:
        query = query.filter(model.created_at >= start_date)
    if end_date:
        query = query.filter(model.created_at <= end_date)
    return query

def apply_rbac_filter(query, model, current_user):
    if current_user.role.name not in READ_ALL_CRM_ROLES:
        return query.filter(model.owner_id == current_user.id)
    return query

@router.get("/sales", dependencies=[Depends(require_permission("reports.read"))])
def get_sales_report(
    db: SessionDep,
    current_user: CurrentActiveUser,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    owner_id: Optional[int] = None,
) -> Any:
    q = db.query(
        func.count(Deal.id).label("total_deals"),
        func.sum(Deal.value).label("total_value"),
        func.avg(Deal.value).label("avg_value")
    )
    q = apply_rbac_filter(q, Deal, current_user)
    q = apply_date_filter(q, Deal, start_date, end_date)
    
    if owner_id and current_user.role.name in READ_ALL_CRM_ROLES:
        q = q.filter(Deal.owner_id == owner_id)
        
    result = q.first()
    return {
        "total_deals": result.total_deals or 0,
        "total_value": float(result.total_value or 0),
        "avg_value": float(result.avg_value or 0)
    }

@router.get("/leads", dependencies=[Depends(require_permission("reports.read"))])
def get_leads_report(
    db: SessionDep,
    current_user: CurrentActiveUser,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[str] = None,
) -> Any:
    q = db.query(
        Lead.status,
        func.count(Lead.id).label("count")
    )
    q = apply_rbac_filter(q, Lead, current_user)
    q = apply_date_filter(q, Lead, start_date, end_date)
    
    if status:
        q = q.filter(Lead.status == status)
        
    q = q.group_by(Lead.status)
    results = q.all()
    
    return {
        "total_leads": sum(r.count for r in results),
        "by_status": {r.status: r.count for r in results}
    }

@router.get("/deals", dependencies=[Depends(require_permission("reports.read"))])
def get_deals_report(
    db: SessionDep,
    current_user: CurrentActiveUser,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    pipeline_id: Optional[int] = None,
) -> Any:
    q = db.query(
        Deal.stage_id,
        func.count(Deal.id).label("count"),
        func.sum(Deal.value).label("value")
    )
    q = apply_rbac_filter(q, Deal, current_user)
    q = apply_date_filter(q, Deal, start_date, end_date)
    
    if pipeline_id:
        q = q.filter(Deal.pipeline_id == pipeline_id)
        
    q = q.group_by(Deal.stage_id)
    results = q.all()
    
    return {
        "total_deals": sum(r.count for r in results),
        "total_value": float(sum(r.value for r in results if r.value) or 0),
        "by_stage": [{"stage_id": r.stage_id, "count": r.count, "value": float(r.value or 0)} for r in results]
    }

@router.get("/tasks", dependencies=[Depends(require_permission("reports.read"))])
def get_tasks_report(
    db: SessionDep,
    current_user: CurrentActiveUser,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Any:
    q = db.query(
        Task.status,
        func.count(Task.id).label("count")
    )
    if current_user.role.name not in READ_ALL_CRM_ROLES:
        from sqlalchemy import or_
        q = q.filter(or_(Task.owner_id == current_user.id, Task.assigned_to_id == current_user.id))
        
    q = apply_date_filter(q, Task, start_date, end_date)
    q = q.group_by(Task.status)
    results = q.all()
    
    return {
        "total_tasks": sum(r.count for r in results),
        "by_status": {r.status: r.count for r in results}
    }

@router.get("/team", dependencies=[Depends(require_permission("reports.read"))])
def get_team_report(
    db: SessionDep,
    current_user: CurrentActiveUser,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Any:
    if current_user.role.name not in READ_ALL_CRM_ROLES:
        return {"error": "Not enough permissions to view team report"}
        
    q = db.query(
        User.id,
        User.name,
        func.count(Deal.id).label("deals_count"),
        func.sum(Deal.value).label("deals_value")
    ).outerjoin(Deal, Deal.owner_id == User.id)
    
    if start_date:
        q = q.filter(Deal.created_at >= start_date)
    if end_date:
        q = q.filter(Deal.created_at <= end_date)
        
    q = q.group_by(User.id, User.name)
    results = q.all()
    
    return {
        "team_performance": [
            {
                "user_id": r.id, 
                "name": r.name, 
                "deals_count": r.deals_count, 
                "deals_value": float(r.deals_value or 0)
            } for r in results
        ]
    }
