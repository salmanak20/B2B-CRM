from decimal import Decimal
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from app.api.deps import SessionDep, CurrentActiveUser, require_permission
from app.api.ownership import ensure_can_modify_crm_record, ensure_can_read_crm_record
from app.models.lead import Lead
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.pipeline_stage import PipelineStage
from app.crud.audit_log import log_event

router=APIRouter()

class ConvertLead(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True)
    company_id:int | None=None
    company_name:str | None=Field(None,min_length=1,max_length=255)
    contact_id:int | None=None
    first_name:str | None=Field(None,min_length=1,max_length=100)
    last_name:str | None=Field(None,max_length=100)
    email:EmailStr | None=None
    create_deal:bool=True
    pipeline_id:int | None=None
    stage_id:int | None=None

@router.post("/leads/{lead_id}/convert",dependencies=[Depends(require_permission("leads.update"))])
def convert_lead(lead_id:int,body:ConvertLead,db:SessionDep,current_user:CurrentActiveUser):
    lead=db.scalar(select(Lead).where(Lead.id==lead_id).with_for_update())
    if not lead:raise HTTPException(404,"Lead not found")
    ensure_can_modify_crm_record(lead.owner_id,current_user)
    existing=db.scalar(select(Deal).where(Deal.lead_id==lead.id).order_by(Deal.id))
    if lead.status=="converted" and lead.company_id:
        return {"company_id":lead.company_id,"contact_id":lead.contact_id,"deal_id":existing.id if existing else None,"already_converted":True}
    stage=None
    if body.create_deal:
        stage=db.get(PipelineStage,body.stage_id) if body.stage_id else None
        if not stage or stage.pipeline_id!=body.pipeline_id:
            raise HTTPException(422,"Choose a valid pipeline and stage")
    company=db.get(Company,body.company_id or lead.company_id) if (body.company_id or lead.company_id) else None
    if body.company_id is not None and company is None:
        raise HTTPException(422,"Choose a company in the active organization")
    if company:ensure_can_read_crm_record(company.owner_id,current_user)
    if not company:
        if not body.company_name:raise HTTPException(422,"Choose a company or enter a new company name")
        company=db.scalar(select(Company).where(Company.owner_id==lead.owner_id,func.lower(Company.name)==body.company_name.lower()))
        if not company:
            company=Company(name=body.company_name,owner_id=lead.owner_id);db.add(company);db.flush()
    contact=db.get(Contact,body.contact_id or lead.contact_id) if (body.contact_id or lead.contact_id) else None
    if body.contact_id is not None and contact is None:
        raise HTTPException(422,"Choose a contact in the active organization")
    if contact:
        ensure_can_read_crm_record(contact.owner_id,current_user)
        if contact.company_id!=company.id:raise HTTPException(422,"Contact belongs to another company")
    elif body.first_name:
        if body.email:
            contact=db.scalar(select(Contact).where(Contact.owner_id==lead.owner_id,func.lower(Contact.email)==str(body.email).lower()))
            if contact and contact.company_id!=company.id:raise HTTPException(409,"Contact email already belongs to another company")
        if not contact:
            contact=Contact(first_name=body.first_name,last_name=body.last_name,email=str(body.email) if body.email else None,
                name=" ".join(filter(None,[body.first_name,body.last_name])),company_id=company.id,owner_id=lead.owner_id)
            db.add(contact);db.flush()
    lead.company_id=company.id;lead.contact_id=contact.id if contact else None;lead.status="converted"
    deal=existing
    if body.create_deal and not deal:
        deal=Deal(title=lead.title,owner_id=lead.owner_id,company_id=company.id,contact_id=lead.contact_id,lead_id=lead.id,
                  pipeline_id=body.pipeline_id,stage_id=stage.id,value=Decimal(lead.estimated_value or 0),probability=stage.probability,
                  status="won" if stage.is_won else "lost" if stage.is_lost else "open")
        if stage.is_closed:
            from datetime import datetime,timezone
            deal.closed_at=datetime.now(timezone.utc)
        db.add(deal);db.flush()
    db.commit()
    from app.api.routes.workspace import run_lead_workflows
    run_lead_workflows(db,lead)
    log_event(db,"Lead Converted",current_user.id,"Lead",lead.id,"Lead linked to company, contact and opportunity")
    return {"company_id":company.id,"contact_id":lead.contact_id,"deal_id":deal.id if deal else None,"already_converted":False}
