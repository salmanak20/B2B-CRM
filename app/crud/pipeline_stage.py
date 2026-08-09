from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.deal import Deal
from app.models.pipeline_stage import PipelineStage
from app.schemas.pipeline_stage import PipelineStageCreate, PipelineStageUpdate


def create_pipeline_stage(db: Session, pipeline_id: int, stage_in: PipelineStageCreate) -> PipelineStage:
    db_stage = PipelineStage(**stage_in.model_dump(), pipeline_id=pipeline_id)
    db.add(db_stage)
    db.commit()
    db.refresh(db_stage)
    return db_stage


def get_pipeline_stage(db: Session, stage_id: int) -> Optional[PipelineStage]:
    return db.scalars(select(PipelineStage).where(PipelineStage.id == stage_id)).first()


def get_pipeline_stage_by_order(db: Session, pipeline_id: int, order: int) -> Optional[PipelineStage]:
    return db.scalars(
        select(PipelineStage).where(PipelineStage.pipeline_id == pipeline_id, PipelineStage.order == order)
    ).first()


def get_pipeline_stage_by_name(db: Session, pipeline_id: int, name: str) -> Optional[PipelineStage]:
    return db.scalars(
        select(PipelineStage).where(PipelineStage.pipeline_id == pipeline_id, func.lower(PipelineStage.name) == name.lower())
    ).first()


def get_pipeline_stages(
    db: Session,
    pipeline_id: int,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[PipelineStage], int]:
    query = select(PipelineStage).where(PipelineStage.pipeline_id == pipeline_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(PipelineStage.order, PipelineStage.id).offset(skip).limit(limit)).all())
    return items, total


def update_pipeline_stage(db: Session, db_stage: PipelineStage, stage_in: PipelineStageUpdate) -> PipelineStage:
    update_data = stage_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_stage, field, value)
    if db_stage.is_won or db_stage.is_lost:
        db_stage.is_closed = True
    db.add(db_stage)
    db.commit()
    db.refresh(db_stage)
    return db_stage


def delete_pipeline_stage(db: Session, db_stage: PipelineStage) -> None:
    db.delete(db_stage)
    db.commit()


def count_stage_deals(db: Session, stage_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Deal).where(Deal.stage_id == stage_id)) or 0
