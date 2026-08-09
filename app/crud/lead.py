from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from app.models.lead import Lead
from app.schemas.lead import LeadCreate, LeadUpdate
from typing import Optional, List, Tuple

def create_lead(db: Session, lead_in: LeadCreate, owner_id: int) -> Lead:
    data = lead_in.model_dump(exclude={"owner_id"})
    data["name"] = data["title"]
    db_lead = Lead(**data, owner_id=owner_id)
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)
    return db_lead

def get_lead(db: Session, lead_id: int) -> Optional[Lead]:
    return db.scalars(select(Lead).where(Lead.id == lead_id)).first()

def get_leads(
    db: Session, 
    skip: int = 0, 
    limit: int = 20, 
    search: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    owner_id: Optional[int] = None,
    company_id: Optional[int] = None,
    contact_id: Optional[int] = None,
) -> Tuple[List[Lead], int]:
    query = select(Lead)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                Lead.name.ilike(search_pattern),
                Lead.title.ilike(search_pattern),
                Lead.description.ilike(search_pattern),
            )
        )
    if status is not None:
        query = query.where(Lead.status == status)
    if source is not None:
        query = query.where(Lead.source == source)
    if owner_id is not None:
        query = query.where(Lead.owner_id == owner_id)
    if company_id is not None:
        query = query.where(Lead.company_id == company_id)
    if contact_id is not None:
        query = query.where(Lead.contact_id == contact_id)
        
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.offset(skip).limit(limit)).all())
    return items, total

def update_lead(db: Session, db_lead: Lead, lead_in: LeadUpdate) -> Lead:
    update_data = lead_in.model_dump(exclude_unset=True)
    if update_data.get("owner_id") is None:
        update_data.pop("owner_id", None)
    for field, value in update_data.items():
        setattr(db_lead, field, value)
    if "title" in update_data:
        db_lead.name = db_lead.title
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)
    return db_lead

def delete_lead(db: Session, db_lead: Lead) -> None:
    db.delete(db_lead)
    db.commit()
