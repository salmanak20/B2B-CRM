from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.deal import Deal
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.schemas.pipeline import PipelineCreate, PipelineUpdate


def create_pipeline(db: Session, pipeline_in: PipelineCreate) -> Pipeline:
    db_pipeline = Pipeline(**pipeline_in.model_dump())
    db.add(db_pipeline)
    db.commit()
    db.refresh(db_pipeline)
    return db_pipeline


def get_pipeline(db: Session, pipeline_id: int) -> Optional[Pipeline]:
    return db.scalars(select(Pipeline).where(Pipeline.id == pipeline_id)).first()


def get_pipeline_by_name(db: Session, name: str) -> Optional[Pipeline]:
    return db.scalars(select(Pipeline).where(func.lower(Pipeline.name) == name.lower())).first()


def get_pipelines(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Tuple[List[Pipeline], int]:
    query = select(Pipeline)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(or_(Pipeline.name.ilike(search_pattern), Pipeline.description.ilike(search_pattern)))
    if is_active is not None:
        query = query.where(Pipeline.is_active == is_active)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(Pipeline.id).offset(skip).limit(limit)).all())
    return items, total


def update_pipeline(db: Session, db_pipeline: Pipeline, pipeline_in: PipelineUpdate) -> Pipeline:
    update_data = pipeline_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_pipeline, field, value)
    db.add(db_pipeline)
    db.commit()
    db.refresh(db_pipeline)
    return db_pipeline


def delete_pipeline(db: Session, db_pipeline: Pipeline) -> None:
    db.delete(db_pipeline)
    db.commit()


def count_pipeline_stages(db: Session, pipeline_id: int) -> int:
    return db.scalar(select(func.count()).select_from(PipelineStage).where(PipelineStage.pipeline_id == pipeline_id)) or 0


def count_pipeline_deals(db: Session, pipeline_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Deal).where(Deal.pipeline_id == pipeline_id)) or 0


def get_pipeline_board(db: Session, pipeline_id: int) -> Optional[Pipeline]:
    return db.scalars(
        select(Pipeline)
        .where(Pipeline.id == pipeline_id)
        .options(selectinload(Pipeline.stages).selectinload(PipelineStage.deals))
    ).first()
