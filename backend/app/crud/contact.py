from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from app.models.contact import Contact
from app.schemas.contact import ContactCreate, ContactUpdate
from typing import Optional, List, Tuple

def build_contact_name(first_name: str, last_name: Optional[str]) -> str:
    return " ".join(part for part in [first_name, last_name] if part)

def create_contact(db: Session, contact_in: ContactCreate, owner_id: int) -> Contact:
    data = contact_in.model_dump(exclude={"owner_id"})
    data["name"] = build_contact_name(data["first_name"], data.get("last_name"))
    db_contact = Contact(**data, owner_id=owner_id)
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

def get_contact(db: Session, contact_id: int) -> Optional[Contact]:
    return db.scalars(select(Contact).where(Contact.id == contact_id)).first()

def get_contacts(
    db: Session, 
    skip: int = 0, 
    limit: int = 20, 
    search: Optional[str] = None,
    company_id: Optional[int] = None,
    owner_id: Optional[int] = None,
) -> Tuple[List[Contact], int]:
    query = select(Contact)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                Contact.name.ilike(search_pattern),
                Contact.first_name.ilike(search_pattern),
                Contact.last_name.ilike(search_pattern),
                Contact.email.ilike(search_pattern),
                Contact.phone.ilike(search_pattern),
                Contact.job_title.ilike(search_pattern)
            )
        )
    if company_id is not None:
        query = query.where(Contact.company_id == company_id)
    if owner_id is not None:
        query = query.where(Contact.owner_id == owner_id)
        
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.offset(skip).limit(limit)).all())
    return items, total

def update_contact(db: Session, db_contact: Contact, contact_in: ContactUpdate) -> Contact:
    update_data = contact_in.model_dump(exclude_unset=True)
    if update_data.get("owner_id") is None:
        update_data.pop("owner_id", None)
    for field, value in update_data.items():
        setattr(db_contact, field, value)
    if "first_name" in update_data or "last_name" in update_data:
        db_contact.name = build_contact_name(db_contact.first_name, db_contact.last_name)
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

def delete_contact(db: Session, db_contact: Contact) -> None:
    db.delete(db_contact)
    db.commit()
