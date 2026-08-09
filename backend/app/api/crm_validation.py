from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.ownership import ensure_can_read_crm_record
from app.crud.company import get_company
from app.crud.contact import get_contact
from app.crud.deal import get_deal
from app.crud.lead import get_lead
from app.models.user import User


def validate_crm_relationships(
    db: Session,
    current_user: User,
    company_id: int | None,
    contact_id: int | None,
    lead_id: int | None,
    deal_id: int | None,
) -> None:
    company = None
    contact = None
    lead = None
    deal = None

    if company_id is not None:
        company = get_company(db, company_id)
        if not company:
            raise HTTPException(status_code=400, detail="Referenced company does not exist")
        ensure_can_read_crm_record(company.owner_id, current_user)
    if contact_id is not None:
        contact = get_contact(db, contact_id)
        if not contact:
            raise HTTPException(status_code=400, detail="Referenced contact does not exist")
        ensure_can_read_crm_record(contact.owner_id, current_user)
    if lead_id is not None:
        lead = get_lead(db, lead_id)
        if not lead:
            raise HTTPException(status_code=400, detail="Referenced lead does not exist")
        ensure_can_read_crm_record(lead.owner_id, current_user)
    if deal_id is not None:
        deal = get_deal(db, deal_id)
        if not deal:
            raise HTTPException(status_code=400, detail="Referenced deal does not exist")
        ensure_can_read_crm_record(deal.owner_id, current_user)

    if company and contact and contact.company_id != company.id:
        raise HTTPException(status_code=400, detail="Contact does not belong to the selected company")
    if company and lead and lead.company_id is not None and lead.company_id != company.id:
        raise HTTPException(status_code=400, detail="Lead does not belong to the selected company")
    if contact and lead and lead.contact_id is not None and lead.contact_id != contact.id:
        raise HTTPException(status_code=400, detail="Lead does not belong to the selected contact")
    if deal and company and deal.company_id is not None and deal.company_id != company.id:
        raise HTTPException(status_code=400, detail="Deal does not belong to the selected company")
    if deal and contact and deal.contact_id is not None and deal.contact_id != contact.id:
        raise HTTPException(status_code=400, detail="Deal does not belong to the selected contact")
    if deal and lead and deal.lead_id is not None and deal.lead_id != lead.id:
        raise HTTPException(status_code=400, detail="Deal does not belong to the selected lead")
