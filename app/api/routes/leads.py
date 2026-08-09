from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.api.deps import SessionDep, CurrentActiveUser, require_permission
from app.api.ownership import (
    can_read_crm_record,
    ensure_can_modify_crm_record,
    ensure_can_read_crm_record,
    resolve_owner_id,
)
from app.schemas.lead import LeadCreate, LeadSource, LeadStatus, LeadUpdate, LeadResponse, LeadList
from app.crud.lead import create_lead, get_lead, get_leads, update_lead, delete_lead
from app.crud.company import get_company
from app.crud.contact import get_contact

router = APIRouter()

def validate_lead_relationships(
    db: SessionDep,
    current_user: CurrentActiveUser,
    company_id: int | None,
    contact_id: int | None,
) -> None:
    company = None
    contact = None
    if company_id is not None:
        company = get_company(db=db, company_id=company_id)
        if not company:
            raise HTTPException(status_code=400, detail="Referenced company does not exist")
        ensure_can_read_crm_record(company.owner_id, current_user)
    if contact_id is not None:
        contact = get_contact(db=db, contact_id=contact_id)
        if not contact:
            raise HTTPException(status_code=400, detail="Referenced contact does not exist")
        ensure_can_read_crm_record(contact.owner_id, current_user)
    if company and contact and contact.company_id != company.id:
        raise HTTPException(status_code=400, detail="Contact does not belong to the selected company")

@router.post("", response_model=LeadResponse, dependencies=[Depends(require_permission("leads.create"))])
def create_new_lead(lead_in: LeadCreate, db: SessionDep, current_user: CurrentActiveUser):
    validate_lead_relationships(db, current_user, lead_in.company_id, lead_in.contact_id)
    owner_id = resolve_owner_id(db, current_user, lead_in.owner_id)
    return create_lead(db=db, lead_in=lead_in, owner_id=owner_id)

@router.get("", response_model=LeadList, dependencies=[Depends(require_permission("leads.read"))])
def read_leads(
    db: SessionDep,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[LeadStatus] = None,
    source: Optional[LeadSource] = None,
    owner_id: Optional[int] = None,
    company_id: Optional[int] = None,
    contact_id: Optional[int] = None,
):
    skip = (page - 1) * page_size
    scoped_owner_id = owner_id
    if not can_read_crm_record(owner_id or current_user.id, current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions to filter by this owner")
    if current_user.role.name not in {"admin", "administrator", "sales_manager", "viewer"}:
        scoped_owner_id = current_user.id
    items, total = get_leads(
        db=db, skip=skip, limit=page_size, search=search,
        status=status, source=source, owner_id=scoped_owner_id, company_id=company_id, contact_id=contact_id
    )
    pages = (total + page_size - 1) // page_size if total > 0 else 0
    return LeadList(items=items, page=page, page_size=page_size, total=total, pages=pages)

@router.get("/{lead_id}", response_model=LeadResponse, dependencies=[Depends(require_permission("leads.read"))])
def read_lead(lead_id: int, db: SessionDep, current_user: CurrentActiveUser):
    lead = get_lead(db=db, lead_id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    ensure_can_read_crm_record(lead.owner_id, current_user)
    return lead

@router.put("/{lead_id}", response_model=LeadResponse, dependencies=[Depends(require_permission("leads.update"))])
def update_existing_lead(lead_id: int, lead_in: LeadUpdate, db: SessionDep, current_user: CurrentActiveUser):
    lead = get_lead(db=db, lead_id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    ensure_can_modify_crm_record(lead.owner_id, current_user)
    update_data = lead_in.model_dump(exclude_unset=True)
    final_company_id = update_data.get("company_id", lead.company_id)
    final_contact_id = update_data.get("contact_id", lead.contact_id)
    validate_lead_relationships(db, current_user, final_company_id, final_contact_id)
    if lead_in.owner_id is not None:
        lead_in.owner_id = resolve_owner_id(db, current_user, lead_in.owner_id)
            
    return update_lead(db=db, db_lead=lead, lead_in=lead_in)

@router.delete("/{lead_id}", dependencies=[Depends(require_permission("leads.delete"))])
def delete_existing_lead(lead_id: int, db: SessionDep, current_user: CurrentActiveUser):
    lead = get_lead(db=db, lead_id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    ensure_can_modify_crm_record(lead.owner_id, current_user)
    delete_lead(db=db, db_lead=lead)
    return {"ok": True}
