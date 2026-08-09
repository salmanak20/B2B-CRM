from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.deps import CurrentActiveUser, SessionDep, require_permission
from app.api.ownership import (
    can_read_crm_record,
    ensure_can_modify_crm_record,
    ensure_can_read_crm_record,
    resolve_owner_id,
)
from app.crud.company import get_company
from app.crud.contact import get_contact
from app.crud.deal import create_deal, delete_deal, get_deal, get_deals, move_deal_stage, update_deal
from app.crud.lead import get_lead
from app.crud.pipeline import get_pipeline
from app.crud.pipeline_stage import get_pipeline_stage
from app.models.activity import Activity
from app.models.task import Task
from app.schemas.deal import DealCreate, DealList, DealResponse, DealStageUpdate, DealStatus, DealUpdate
from app.schemas.timeline import TimelineItem, TimelineResponse

router = APIRouter()


def validate_pipeline_and_stage(db: SessionDep, pipeline_id: int, stage_id: int):
    pipeline = get_pipeline(db, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=400, detail="Referenced pipeline does not exist")
    stage = get_pipeline_stage(db, stage_id)
    if not stage:
        raise HTTPException(status_code=400, detail="Referenced pipeline stage does not exist")
    if stage.pipeline_id != pipeline.id:
        raise HTTPException(status_code=400, detail="Pipeline stage does not belong to the selected pipeline")
    return pipeline, stage


def validate_deal_relationships(
    db: SessionDep,
    current_user: CurrentActiveUser,
    company_id: int | None,
    contact_id: int | None,
    lead_id: int | None,
) -> None:
    company = None
    contact = None
    lead = None
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

    if company and contact and contact.company_id != company.id:
        raise HTTPException(status_code=400, detail="Contact does not belong to the selected company")
    if company and lead and lead.company_id is not None and lead.company_id != company.id:
        raise HTTPException(status_code=400, detail="Lead does not belong to the selected company")
    if contact and lead and lead.contact_id is not None and lead.contact_id != contact.id:
        raise HTTPException(status_code=400, detail="Lead does not belong to the selected contact")


@router.post("", response_model=DealResponse, dependencies=[Depends(require_permission("deals.create"))])
def create_new_deal(deal_in: DealCreate, db: SessionDep, current_user: CurrentActiveUser):
    _, stage = validate_pipeline_and_stage(db, deal_in.pipeline_id, deal_in.stage_id)
    validate_deal_relationships(db, current_user, deal_in.company_id, deal_in.contact_id, deal_in.lead_id)
    owner_id = resolve_owner_id(db, current_user, deal_in.owner_id)
    return create_deal(db, deal_in, owner_id, stage)


@router.get("", response_model=DealList, dependencies=[Depends(require_permission("deals.read"))])
def read_deals(
    db: SessionDep,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    owner_id: Optional[int] = None,
    pipeline_id: Optional[int] = None,
    stage_id: Optional[int] = None,
    company_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    status: Optional[DealStatus] = None,
):
    skip = (page - 1) * page_size
    scoped_owner_id = owner_id
    if not can_read_crm_record(owner_id or current_user.id, current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions to filter by this owner")
    if current_user.role.name not in {"admin", "administrator", "sales_manager", "viewer"}:
        scoped_owner_id = current_user.id
    items, total = get_deals(
        db,
        skip=skip,
        limit=page_size,
        search=search,
        owner_id=scoped_owner_id,
        pipeline_id=pipeline_id,
        stage_id=stage_id,
        company_id=company_id,
        contact_id=contact_id,
        lead_id=lead_id,
        status=status,
    )
    pages = (total + page_size - 1) // page_size if total else 0
    return DealList(items=items, page=page, page_size=page_size, total=total, pages=pages)


@router.get("/{deal_id}", response_model=DealResponse, dependencies=[Depends(require_permission("deals.read"))])
def read_deal(deal_id: int, db: SessionDep, current_user: CurrentActiveUser):
    deal = get_deal(db, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    ensure_can_read_crm_record(deal.owner_id, current_user)
    return deal


@router.get("/{deal_id}/timeline", response_model=TimelineResponse, dependencies=[Depends(require_permission("deals.read"))])
def read_deal_timeline(
    deal_id: int,
    db: SessionDep,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    deal = get_deal(db, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    ensure_can_read_crm_record(deal.owner_id, current_user)

    activities = list(db.scalars(select(Activity).where(Activity.deal_id == deal_id)).all())
    tasks = list(db.scalars(select(Task).where(Task.deal_id == deal_id)).all())
    sortable_items = [
        (
            activity.occurred_at,
            TimelineItem(
                type="activity",
                id=activity.id,
                title=activity.subject,
                description=activity.description,
                occurred_at=activity.occurred_at,
                activity_type=activity.type,
            ),
        )
        for activity in activities
    ]
    sortable_items.extend(
        (
            task.due_date or task.created_at,
            TimelineItem(
                type="task",
                id=task.id,
                title=task.title,
                description=task.description,
                due_date=task.due_date,
                task_status=task.status,
                task_priority=task.priority,
            ),
        )
        for task in tasks
    )
    sortable_items.sort(key=lambda item: item[0])
    items = [item for _, item in sortable_items]
    total = len(items)
    start = (page - 1) * page_size
    pages = (total + page_size - 1) // page_size if total else 0
    return TimelineResponse(items=items[start : start + page_size], page=page, page_size=page_size, total=total, pages=pages)


@router.put("/{deal_id}", response_model=DealResponse, dependencies=[Depends(require_permission("deals.update"))])
def update_existing_deal(deal_id: int, deal_in: DealUpdate, db: SessionDep, current_user: CurrentActiveUser):
    deal = get_deal(db, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    ensure_can_modify_crm_record(deal.owner_id, current_user)
    update_data = deal_in.model_dump(exclude_unset=True)
    final_pipeline_id = update_data.get("pipeline_id", deal.pipeline_id)
    final_stage_id = update_data.get("stage_id", deal.stage_id)
    _, stage = validate_pipeline_and_stage(db, final_pipeline_id, final_stage_id)
    validate_deal_relationships(
        db,
        current_user,
        update_data.get("company_id", deal.company_id),
        update_data.get("contact_id", deal.contact_id),
        update_data.get("lead_id", deal.lead_id),
    )
    if deal_in.owner_id is not None:
        deal_in.owner_id = resolve_owner_id(db, current_user, deal_in.owner_id)
    return update_deal(db, deal, deal_in, stage=stage)


@router.patch("/{deal_id}/stage", response_model=DealResponse, dependencies=[Depends(require_permission("deals.update"))])
def move_existing_deal_stage(deal_id: int, stage_in: DealStageUpdate, db: SessionDep, current_user: CurrentActiveUser):
    deal = get_deal(db, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    ensure_can_modify_crm_record(deal.owner_id, current_user)
    stage = get_pipeline_stage(db, stage_in.stage_id)
    if not stage:
        raise HTTPException(status_code=400, detail="Referenced pipeline stage does not exist")
    if stage.pipeline_id != deal.pipeline_id:
        raise HTTPException(status_code=400, detail="Pipeline stage does not belong to the deal pipeline")
    return move_deal_stage(db, deal, stage)


@router.delete("/{deal_id}", dependencies=[Depends(require_permission("deals.delete"))])
def delete_existing_deal(deal_id: int, db: SessionDep, current_user: CurrentActiveUser):
    deal = get_deal(db, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    ensure_can_modify_crm_record(deal.owner_id, current_user)
    delete_deal(db, deal)
    return {"ok": True}
