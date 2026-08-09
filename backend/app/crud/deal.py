from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.deal import Deal
from app.models.pipeline_stage import PipelineStage
from app.schemas.deal import DealCreate, DealUpdate


def deal_status_for_stage(stage: PipelineStage) -> str:
    if stage.is_won:
        return "won"
    if stage.is_lost:
        return "lost"
    return "open"


def create_deal(db: Session, deal_in: DealCreate, owner_id: int, stage: PipelineStage) -> Deal:
    data = deal_in.model_dump(exclude={"owner_id"})
    data["status"] = deal_status_for_stage(stage)
    db_deal = Deal(**data, owner_id=owner_id)
    db.add(db_deal)
    db.commit()
    db.refresh(db_deal)
    return db_deal


def get_deal(db: Session, deal_id: int) -> Optional[Deal]:
    return db.scalars(select(Deal).where(Deal.id == deal_id)).first()


def get_deals(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    owner_id: Optional[int] = None,
    pipeline_id: Optional[int] = None,
    stage_id: Optional[int] = None,
    company_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    status: Optional[str] = None,
) -> Tuple[List[Deal], int]:
    query = select(Deal)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(or_(Deal.title.ilike(search_pattern), Deal.description.ilike(search_pattern)))
    if owner_id is not None:
        query = query.where(Deal.owner_id == owner_id)
    if pipeline_id is not None:
        query = query.where(Deal.pipeline_id == pipeline_id)
    if stage_id is not None:
        query = query.where(Deal.stage_id == stage_id)
    if company_id is not None:
        query = query.where(Deal.company_id == company_id)
    if contact_id is not None:
        query = query.where(Deal.contact_id == contact_id)
    if lead_id is not None:
        query = query.where(Deal.lead_id == lead_id)
    if status is not None:
        query = query.where(Deal.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(Deal.id).offset(skip).limit(limit)).all())
    return items, total


def update_deal(db: Session, db_deal: Deal, deal_in: DealUpdate, stage: PipelineStage | None = None) -> Deal:
    update_data = deal_in.model_dump(exclude_unset=True)
    if update_data.get("owner_id") is None:
        update_data.pop("owner_id", None)
    for field, value in update_data.items():
        setattr(db_deal, field, value)
    if stage is not None:
        db_deal.status = deal_status_for_stage(stage)
    db.add(db_deal)
    db.commit()
    db.refresh(db_deal)
    return db_deal


def move_deal_stage(db: Session, db_deal: Deal, stage: PipelineStage) -> Deal:
    db_deal.stage_id = stage.id
    db_deal.status = deal_status_for_stage(stage)
    db.add(db_deal)
    db.commit()
    db.refresh(db_deal)
    return db_deal


def delete_deal(db: Session, db_deal: Deal) -> None:
    db.delete(db_deal)
    db.commit()
