from fastapi import APIRouter, Depends
from typing import Any
from app.api.deps import SessionDep, CurrentActiveUser
from sqlalchemy import or_

from app.models.company import Company
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.deal import Deal
from app.models.task import Task
from app.api.ownership import READ_ALL_CRM_ROLES

router = APIRouter()

@router.get("/", response_model=dict)
def global_search(
    q: str,
    db: SessionDep,
    current_user: CurrentActiveUser,
) -> Any:
    """
    Search across Companies, Contacts, Leads, Deals, Tasks.
    """
    results = {
        "companies": [],
        "contacts": [],
        "leads": [],
        "deals": [],
        "tasks": [],
    }
    
    if not q or len(q) < 2:
        return results
        
    search_term = f"%{q}%"
    
    # Base filter for RBAC
    def rbac_filter(query, model):
        if current_user.role.name not in READ_ALL_CRM_ROLES:
            if hasattr(model, 'owner_id'):
                return query.filter(model.owner_id == current_user.id)
            elif hasattr(model, 'assigned_to_id'):
                return query.filter(
                    or_(model.owner_id == current_user.id, model.assigned_to_id == current_user.id)
                )
        return query

    # Companies
    comp_q = db.query(Company).filter(
        or_(
            Company.name.ilike(search_term),
            Company.industry.ilike(search_term),
            Company.website.ilike(search_term)
        )
    )
    comp_q = rbac_filter(comp_q, Company)
    for c in comp_q.limit(10).all():
        results["companies"].append({"id": c.id, "name": c.name, "industry": c.industry})
        
    # Contacts
    cont_q = db.query(Contact).filter(
        or_(
            Contact.first_name.ilike(search_term),
            Contact.last_name.ilike(search_term),
            Contact.email.ilike(search_term)
        )
    )
    cont_q = rbac_filter(cont_q, Contact)
    for c in cont_q.limit(10).all():
        results["contacts"].append({"id": c.id, "name": f"{c.first_name} {c.last_name}", "email": c.email})
        
    # Leads
    lead_q = db.query(Lead).filter(
        or_(
            Lead.title.ilike(search_term),
            Lead.name.ilike(search_term)
        )
    )
    lead_q = rbac_filter(lead_q, Lead)
    for l in lead_q.limit(10).all():
        results["leads"].append({"id": l.id, "title": l.title, "name": l.name})
        
    # Deals
    deal_q = db.query(Deal).filter(
        Deal.title.ilike(search_term)
    )
    deal_q = rbac_filter(deal_q, Deal)
    for d in deal_q.limit(10).all():
        results["deals"].append({"id": d.id, "title": d.title, "value": d.value})
        
    # Tasks
    task_q = db.query(Task).filter(
        or_(
            Task.title.ilike(search_term),
            Task.description.ilike(search_term)
        )
    )
    task_q = rbac_filter(task_q, Task)
    for t in task_q.limit(10).all():
        results["tasks"].append({"id": t.id, "title": t.title, "status": t.status})

    return results
