import csv
import io
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.api.deps import SessionDep, CurrentActiveUser
from app.api.ownership import ensure_can_read_crm_record
from app.models.company import Company
from app.models.contact import Contact
from app.models.lead import Lead
from app.schemas.company import CompanyCreate
from app.schemas.contact import ContactCreate
from app.schemas.lead import LeadCreate
from app.crud.audit_log import log_event

router=APIRouter()
MODELS={"companies":(Company,CompanyCreate),"contacts":(Contact,ContactCreate),"leads":(Lead,LeadCreate)}

class ImportCSV(BaseModel):
    csv_text:str=Field(max_length=2*1024*1024)
    mapping:dict[str,str]
    mode:Literal["skip","update"]="skip"

def rows_for_import(entity,body,db,user):
    if entity not in MODELS:raise HTTPException(404,"Unsupported import type")
    permissions={p.name for p in user.role.permissions}
    if f"{entity}.create" not in permissions or (body.mode=="update" and f"{entity}.update" not in permissions):
        raise HTTPException(403,"Insufficient import permissions")
    model,schema=MODELS[entity]
    allowed=set(schema.model_fields)-{"owner_id"}
    if set(body.mapping)-allowed-{"company_name"}:
        raise HTTPException(422,"Mapping contains unsupported or restricted fields")
    try:
        reader=csv.DictReader(io.StringIO(body.csv_text.lstrip('\ufeff')),strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames):
            raise HTTPException(422,"CSV needs unique column headings")
        if any(column not in reader.fieldnames for column in body.mapping.values()):
            raise HTTPException(422,"Mapped column does not exist in the CSV")
        source=[]
        for index,row in enumerate(reader):
            if index>=1000:raise HTTPException(413,"Import at most 1000 rows per file")
            source.append(row)
    except csv.Error:
        raise HTTPException(422,"The CSV file is malformed")
    output=[];seen=set()
    for number,row in enumerate(source,2):
        item={"row":number,"status":"valid","errors":[],"data":{},"existing_id":None}
        try:
            if None in row:raise ValueError("Row has more columns than the header")
            data={field:row.get(column,"").strip() for field,column in body.mapping.items() if row.get(column,"").strip()}
            company_name=data.pop("company_name",None)
            if company_name:
                query=select(Company).where(func.lower(Company.name)==company_name.lower())
                if user.role.name not in {"admin","sales_manager","viewer"}:query=query.where(Company.owner_id==user.id)
                matches=db.scalars(query.limit(2)).all()
                if len(matches)!=1:raise ValueError("Company name is missing or ambiguous; map a company ID instead")
                data["company_id"]=matches[0].id
            if entity=="leads":data.setdefault("status","new")
            parsed=schema.model_validate(data)
            for field,related_model in [("company_id",Company),("contact_id",Contact)]:
                record_id=getattr(parsed,field,None)
                if record_id:
                    related=db.get(related_model,record_id)
                    if not related:raise ValueError(f"{field} does not exist")
                    ensure_can_read_crm_record(related.owner_id,user)
            if getattr(parsed,"contact_id",None) and getattr(parsed,"company_id",None):
                if db.get(Contact,parsed.contact_id).company_id!=parsed.company_id:
                    raise ValueError("Contact does not belong to selected company")
            field="name" if entity=="companies" else "email" if entity=="contacts" else "title"
            value=getattr(parsed,field,None)
            if entity=="contacts" and not value:
                raise ValueError("CSV contacts require an email for duplicate detection")
            key=str(value).casefold()
            if key in seen:raise ValueError("Duplicate identifier within this file; keep one row")
            seen.add(key)
            existing=db.scalar(select(model).where(model.owner_id==user.id,func.lower(getattr(model,field))==key))
            item.update(data=parsed.model_dump(mode="json",exclude={"owner_id"}),existing_id=existing.id if existing else None,
                        status="duplicate" if existing else "valid")
        except (ValueError,ValidationError,HTTPException) as error:
            item["status"]="invalid"
            item["errors"]=[str(error.detail) if isinstance(error,HTTPException) else str(error)]
        output.append(item)
    return output

@router.post("/imports/{entity}/preview")
def preview(entity:str,body:ImportCSV,db:SessionDep,current_user:CurrentActiveUser):
    rows=rows_for_import(entity,body,db,current_user)
    return {"rows":rows,"total":len(rows),"valid":sum(r['status']=='valid' for r in rows),
            "duplicates":sum(r['status']=='duplicate' for r in rows),"invalid":sum(r['status']=='invalid' for r in rows)}

@router.post("/imports/{entity}/commit")
def commit(entity:str,body:ImportCSV,db:SessionDep,current_user:CurrentActiveUser):
    rows=rows_for_import(entity,body,db,current_user)
    model,schema=MODELS[entity];counts={"created":0,"updated":0,"skipped":0,"failed":0};errors=[];workflow_leads=[]
    for row in rows:
        if row['status']=='invalid':
            counts['failed']+=1;errors.append({"row":row['row'],"error":"; ".join(row['errors'])});continue
        if row['existing_id'] and body.mode=='skip':counts['skipped']+=1;continue
        try:
            with db.begin_nested():
                data=schema.model_validate(row['data']).model_dump(mode="json",exclude={"owner_id"})
                if entity=='contacts':data['name']=' '.join(filter(None,[data['first_name'],data.get('last_name')]))
                if entity=='leads':data['name']=data['title']
                existing=db.get(model,row['existing_id']) if row['existing_id'] else None
                if existing:
                    # Only mapped fields change; unmapped optional fields are preserved.
                    keys=set(body.mapping)|({'company_id'} if 'company_name' in body.mapping else set())
                    for key,value in data.items():
                        if key in keys or key=='name' and entity in {'leads','contacts'}:setattr(existing,key,value)
                else:
                    existing_created=model(**data,owner_id=current_user.id)
                    db.add(existing_created)
                db.flush()
                if entity=='leads':workflow_leads.append((existing or existing_created).id)
            counts['updated' if existing else 'created']+=1
        except (IntegrityError,ValueError):
            counts['failed']+=1;errors.append({"row":row['row'],"error":"Record conflicts with existing or related data"})
    db.commit()
    if entity=='leads':
        from app.api.routes.workspace import run_lead_workflows
        for lead_id in workflow_leads:run_lead_workflows(db,db.get(Lead,lead_id))
    log_event(db,"CSV Imported",current_user.id,entity,None,f"Created {counts['created']}, updated {counts['updated']}, skipped {counts['skipped']}, failed {counts['failed']}")
    return {**counts,"errors":errors}
