from datetime import datetime, timezone, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.api.deps import SessionDep, CurrentActiveUser, require_role
from app.api.ownership import can_read_crm_record, ensure_can_read_crm_record, ensure_can_modify_crm_record
from app.models.workspace import WorkspaceSettings, WorkflowRule, WorkflowRun
from app.models.company import Company
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.deal import Deal
from app.models.task import Task
from app.models.activity import Activity
from app.models.user import User
from app.models.role import Role
from app.crud.audit_log import log_event
from app.crud.notification import create_notification
from app.schemas.notification import NotificationCreate

router=APIRouter()
MODELS={"companies":Company,"contacts":Contact,"leads":Lead,"deals":Deal,"tasks":Task}

def ensure_no_attachments(db,entity,record_id):
    from app.models.workspace import Attachment
    if db.scalar(select(Attachment.id).where(Attachment.entity==entity,Attachment.entity_id==record_id).limit(1)):
        raise HTTPException(409,'Remove private attachments before deleting this record.')

def checked_record(db,entity,record_id,user,write=False):
    model=MODELS.get(entity)
    record=db.get(model,record_id) if model else None
    if not record:
        raise HTTPException(404,"Record not found")
    if write:
        ensure_can_modify_crm_record(record.owner_id,user)
    else:
        ensure_can_read_crm_record(record.owner_id,user)
    return record

def notify_assignment(db,task):
    if task.assigned_to_id:
        create_notification(db,NotificationCreate(user_id=task.assigned_to_id,title="Task assigned",message=task.title,
                            notification_type="task_assigned",related_entity="task",related_entity_id=task.id))

@router.get("/roles",dependencies=[Depends(require_role(["admin"]))])
def roles(db:SessionDep,current_user:CurrentActiveUser):
    return [{"id":r.id,"name":r.name,"description":r.description} for r in db.scalars(select(Role)).all()]

@router.get("/workspace")
def workspace(db:SessionDep,current_user:CurrentActiveUser):
    row=db.scalar(select(WorkspaceSettings))
    return {"name":row.name if row else "CRM Pro","timezone":row.timezone if row else "UTC","currency":row.currency if row else "USD"}

class WorkspaceUpdate(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=100)
    timezone:str="UTC"
    currency:Literal["USD"]="USD"

@router.put("/workspace",dependencies=[Depends(require_role(["admin"]))])
def update_workspace(body:WorkspaceUpdate,db:SessionDep,current_user:CurrentActiveUser):
    try:ZoneInfo(body.timezone)
    except ZoneInfoNotFoundError:raise HTTPException(422,"Use a valid IANA timezone")
    row=db.scalar(select(WorkspaceSettings))
    if not row:
        row=WorkspaceSettings(**body.model_dump());db.add(row)
    else:
        for key,value in body.model_dump().items():setattr(row,key,value)
    db.commit()
    log_event(db,"Workspace Updated",current_user.id,"Workspace",row.id,"Workspace name and timezone updated")
    return body

@router.get("/directory")
def directory(db:SessionDep,current_user:CurrentActiveUser):
    from app.models.membership import Membership
    # Names and IDs only; full account/email administration remains administrator-only.
    if current_user.role.name not in {"admin","sales_manager"}:
        return [{"id":current_user.id,"name":current_user.name}]
    return [{"id":u.id,"name":u.name} for u in db.scalars(select(User).join(Membership).where(
        User.is_active.is_(True),Membership.organization_id==current_user.organization_id,
        Membership.is_active.is_(True)).order_by(User.name)).all()]

@router.get("/records/{entity}/{record_id}/related")
def related(entity:str,record_id:int,db:SessionDep,current_user:CurrentActiveUser):
    checked_record(db,entity,record_id,current_user)
    field={"companies":"company_id","contacts":"contact_id","leads":"lead_id","deals":"deal_id"}.get(entity)
    if not field:raise HTTPException(422,"Unsupported related-record type")
    from fastapi.encoders import jsonable_encoder
    result={}
    for name,model in {**MODELS,"activities":Activity}.items():
        if hasattr(model,field):
            query=select(model).where(getattr(model,field)==record_id)
            owner=model.user_id if model is Activity else model.owner_id
            if current_user.role.name not in {"admin","sales_manager","viewer"}:
                query=query.where(owner==current_user.id)
            # A bounded related overview has explicit counts; full lists retain filters/paging.
            records=db.scalars(query.order_by(model.id.desc()).limit(100)).all()
            result[name]=jsonable_encoder(records)
    return result

class RuleInput(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=100)
    trigger_status:Literal["new","contacted","qualified","nurturing","converted","lost","unqualified"]="qualified"
    min_value:Decimal=Field(0,ge=0)
    assigned_to_id:int | None=None
    task_title:str=Field(min_length=1,max_length=255)
    enabled:bool=True

@router.get("/workflows",dependencies=[Depends(require_role(["admin","sales_manager"]))])
def workflows(db:SessionDep,current_user:CurrentActiveUser):
    return db.scalars(select(WorkflowRule).order_by(WorkflowRule.id)).all()

def validate_assignee(db,user_id,actor=None):
    if user_id:
        from app.db.tenant_session import require_member
        require_member(db,user_id)
        if actor:
            from app.api.ownership import validate_representative
            validate_representative(db,actor,user_id)
        user=db.get(User,user_id)
        if not user or not user.is_active:raise HTTPException(422,"Choose an active assignee")

@router.post("/workflows",dependencies=[Depends(require_role(["admin","sales_manager"]))])
def create_rule(body:RuleInput,db:SessionDep,current_user:CurrentActiveUser):
    validate_assignee(db,body.assigned_to_id,current_user)
    rule=WorkflowRule(**body.model_dump(),owner_id=current_user.id);db.add(rule);db.commit();db.refresh(rule)
    log_event(db,"Workflow Created",current_user.id,"Workflow",rule.id,rule.name)
    db.refresh(rule)
    return rule

@router.put("/workflows/{rule_id}",dependencies=[Depends(require_role(["admin","sales_manager"]))])
def update_rule(rule_id:int,body:RuleInput,db:SessionDep,current_user:CurrentActiveUser):
    rule=db.get(WorkflowRule,rule_id)
    if not rule:raise HTTPException(404,"Workflow not found")
    validate_assignee(db,body.assigned_to_id,current_user)
    for key,value in body.model_dump().items():setattr(rule,key,value)
    db.commit();db.refresh(rule)
    log_event(db,"Workflow Updated",current_user.id,"Workflow",rule.id,rule.name)
    db.refresh(rule)
    return rule

@router.delete("/workflows/{rule_id}",dependencies=[Depends(require_role(["admin","sales_manager"]))])
def delete_rule(rule_id:int,db:SessionDep,current_user:CurrentActiveUser):
    rule=db.get(WorkflowRule,rule_id)
    if not rule:raise HTTPException(404,"Workflow not found")
    db.query(WorkflowRun).filter_by(rule_id=rule_id).delete()
    db.delete(rule);db.commit()
    log_event(db,"Workflow Deleted",current_user.id,"Workflow",rule_id,"Workflow removed")
    return {"ok":True}

def run_lead_workflows(db,lead):
    from app.services.subscriptions import feature_allowed
    from app.db.tenant_session import organization_id
    if not feature_allowed(db,organization_id(db),'workflows'):return
    for rule in db.scalars(select(WorkflowRule).where(WorkflowRule.enabled.is_(True),WorkflowRule.trigger_status==lead.status)).all():
        if Decimal(lead.estimated_value or 0)<rule.min_value:continue
        if db.scalar(select(WorkflowRun).where(WorkflowRun.rule_id==rule.id,WorkflowRun.lead_id==lead.id)):continue
        task=Task(title=rule.task_title,description=f"Workflow: {rule.name}",owner_id=lead.owner_id,
                  assigned_to_id=rule.assigned_to_id or lead.owner_id,lead_id=lead.id,status="pending",priority="medium",
                  due_date=datetime.now(timezone.utc)+timedelta(days=1))
        try:
            with db.begin_nested():
                db.add(task);db.flush();db.add(WorkflowRun(rule_id=rule.id,lead_id=lead.id,task_id=task.id));db.flush()
            db.commit()
        except IntegrityError as error:
            # The unique rule/lead key makes concurrent delivery idempotent.
            if 'CRM_QUOTA:' in str(error.orig):
                raise HTTPException(409,'Workflow or task limit reached. Contact platform administration.')
            continue
        notify_assignment(db,task)

@router.post("/notifications/check-due")
def check_due(db:SessionDep,current_user:CurrentActiveUser):
    from app.services.reminders import deliver_due
    return {"created":deliver_due(db,current_user.id)}
