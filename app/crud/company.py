from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from app.models.company import Company
from app.schemas.company import CompanyCreate, CompanyUpdate
from typing import Optional, List, Tuple

def create_company(db: Session, company_in: CompanyCreate, owner_id: int) -> Company:
    data = company_in.model_dump(mode="json", exclude={"owner_id"})
    db_company = Company(**data, owner_id=owner_id)
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company

def get_company(db: Session, company_id: int) -> Optional[Company]:
    return db.scalars(select(Company).where(Company.id == company_id)).first()

def get_companies(
    db: Session, 
    skip: int = 0, 
    limit: int = 20, 
    search: Optional[str] = None,
    owner_id: Optional[int] = None,
    industry: Optional[str] = None,
) -> Tuple[List[Company], int]:
    query = select(Company)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                Company.name.ilike(search_pattern),
                Company.industry.ilike(search_pattern),
                Company.email.ilike(search_pattern),
                Company.phone.ilike(search_pattern),
                Company.website.ilike(search_pattern),
            )
        )
    if owner_id is not None:
        query = query.where(Company.owner_id == owner_id)
    if industry is not None:
        query = query.where(Company.industry == industry)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.offset(skip).limit(limit)).all())
    return items, total

def get_company_by_owner_and_name(db: Session, owner_id: int, name: str) -> Optional[Company]:
    return db.scalars(
        select(Company).where(Company.owner_id == owner_id, func.lower(Company.name) == name.lower())
    ).first()

def update_company(db: Session, db_company: Company, company_in: CompanyUpdate) -> Company:
    update_data = company_in.model_dump(mode="json", exclude_unset=True)
    if update_data.get("owner_id") is None:
        update_data.pop("owner_id", None)
    for field, value in update_data.items():
        setattr(db_company, field, value)
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company

def delete_company(db: Session, db_company: Company) -> None:
    db.delete(db_company)
    db.commit()
