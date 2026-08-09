from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional

from app.api.deps import SessionDep, CurrentActiveUser, require_permission
from app.api.ownership import (
    can_read_crm_record,
    ensure_can_modify_crm_record,
    ensure_can_read_crm_record,
    resolve_owner_id,
)
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyResponse, CompanyList
from app.crud.company import (
    create_company,
    delete_company,
    get_companies,
    get_company,
    get_company_by_owner_and_name,
    update_company,
)

router = APIRouter()

@router.post("", response_model=CompanyResponse, dependencies=[Depends(require_permission("companies.create"))])
def create_new_company(company_in: CompanyCreate, db: SessionDep, current_user: CurrentActiveUser):
    owner_id = resolve_owner_id(db, current_user, company_in.owner_id)
    if get_company_by_owner_and_name(db, owner_id=owner_id, name=company_in.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A company with this name already exists for the owner",
        )
    return create_company(db=db, company_in=company_in, owner_id=owner_id)

@router.get("", response_model=CompanyList, dependencies=[Depends(require_permission("companies.read"))])
def read_companies(
    db: SessionDep,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    owner_id: Optional[int] = None,
    industry: Optional[str] = None,
):
    skip = (page - 1) * page_size
    scoped_owner_id = owner_id
    if not can_read_crm_record(owner_id or current_user.id, current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions to filter by this owner")
    if current_user.role.name not in {"admin", "administrator", "sales_manager", "viewer"}:
        scoped_owner_id = current_user.id
    items, total = get_companies(
        db=db,
        skip=skip,
        limit=page_size,
        search=search,
        owner_id=scoped_owner_id,
        industry=industry,
    )
    pages = (total + page_size - 1) // page_size if total > 0 else 0
    return CompanyList(items=items, page=page, page_size=page_size, total=total, pages=pages)

@router.get("/{company_id}", response_model=CompanyResponse, dependencies=[Depends(require_permission("companies.read"))])
def read_company(company_id: int, db: SessionDep, current_user: CurrentActiveUser):
    company = get_company(db=db, company_id=company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    ensure_can_read_crm_record(company.owner_id, current_user)
    return company

@router.put("/{company_id}", response_model=CompanyResponse, dependencies=[Depends(require_permission("companies.update"))])
def update_existing_company(company_id: int, company_in: CompanyUpdate, db: SessionDep, current_user: CurrentActiveUser):
    company = get_company(db=db, company_id=company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    ensure_can_modify_crm_record(company.owner_id, current_user)
    if company_in.owner_id is not None:
        company_in.owner_id = resolve_owner_id(db, current_user, company_in.owner_id)
    target_owner_id = company_in.owner_id or company.owner_id
    target_name = company_in.name or company.name
    duplicate = get_company_by_owner_and_name(db, owner_id=target_owner_id, name=target_name)
    if duplicate and duplicate.id != company.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A company with this name already exists for the owner",
        )
    return update_company(db=db, db_company=company, company_in=company_in)

@router.delete("/{company_id}", dependencies=[Depends(require_permission("companies.delete"))])
def delete_existing_company(company_id: int, db: SessionDep, current_user: CurrentActiveUser):
    company = get_company(db=db, company_id=company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    ensure_can_modify_crm_record(company.owner_id, current_user)
    delete_company(db=db, db_company=company)
    return {"ok": True}
