from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.api.deps import SessionDep, CurrentActiveUser, require_permission
from app.api.ownership import (
    can_read_crm_record,
    ensure_can_modify_crm_record,
    ensure_can_read_crm_record,
    resolve_owner_id,
)
from app.schemas.contact import ContactCreate, ContactUpdate, ContactResponse, ContactList
from app.crud.contact import create_contact, get_contact, get_contacts, update_contact, delete_contact
from app.crud.company import get_company

router = APIRouter()

@router.post("", response_model=ContactResponse, dependencies=[Depends(require_permission("contacts.create"))])
def create_new_contact(contact_in: ContactCreate, db: SessionDep, current_user: CurrentActiveUser):
    company = get_company(db=db, company_id=contact_in.company_id)
    if not company:
        raise HTTPException(status_code=400, detail="Referenced company does not exist")
    ensure_can_read_crm_record(company.owner_id, current_user)
    owner_id = resolve_owner_id(db, current_user, contact_in.owner_id)
    return create_contact(db=db, contact_in=contact_in, owner_id=owner_id)

@router.get("", response_model=ContactList, dependencies=[Depends(require_permission("contacts.read"))])
def read_contacts(
    db: SessionDep,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    company_id: Optional[int] = None,
    owner_id: Optional[int] = None,
):
    skip = (page - 1) * page_size
    scoped_owner_id = owner_id
    if not can_read_crm_record(owner_id or current_user.id, current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions to filter by this owner")
    if current_user.role.name not in {"admin", "administrator", "sales_manager", "viewer"}:
        scoped_owner_id = current_user.id
    items, total = get_contacts(
        db=db,
        skip=skip,
        limit=page_size,
        search=search,
        company_id=company_id,
        owner_id=scoped_owner_id,
    )
    pages = (total + page_size - 1) // page_size if total > 0 else 0
    return ContactList(items=items, page=page, page_size=page_size, total=total, pages=pages)

@router.get("/{contact_id}", response_model=ContactResponse, dependencies=[Depends(require_permission("contacts.read"))])
def read_contact(contact_id: int, db: SessionDep, current_user: CurrentActiveUser):
    contact = get_contact(db=db, contact_id=contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    ensure_can_read_crm_record(contact.owner_id, current_user)
    return contact

@router.put("/{contact_id}", response_model=ContactResponse, dependencies=[Depends(require_permission("contacts.update"))])
def update_existing_contact(contact_id: int, contact_in: ContactUpdate, db: SessionDep, current_user: CurrentActiveUser):
    contact = get_contact(db=db, contact_id=contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    ensure_can_modify_crm_record(contact.owner_id, current_user)
        
    if "company_id" in contact_in.model_fields_set and contact_in.company_id is None:
        raise HTTPException(status_code=400, detail="Contact must belong to a company")
    if contact_in.company_id is not None:
        company = get_company(db=db, company_id=contact_in.company_id)
        if not company:
            raise HTTPException(status_code=400, detail="Referenced company does not exist")
        ensure_can_read_crm_record(company.owner_id, current_user)
    if contact_in.owner_id is not None:
        contact_in.owner_id = resolve_owner_id(db, current_user, contact_in.owner_id)
            
    return update_contact(db=db, db_contact=contact, contact_in=contact_in)

@router.delete("/{contact_id}", dependencies=[Depends(require_permission("contacts.delete"))])
def delete_existing_contact(contact_id: int, db: SessionDep, current_user: CurrentActiveUser):
    contact = get_contact(db=db, contact_id=contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    ensure_can_modify_crm_record(contact.owner_id, current_user)
    delete_contact(db=db, db_contact=contact)
    return {"ok": True}
