from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentActiveUser, SessionDep, require_permission
from app.crud.pipeline import get_pipeline
from app.crud.pipeline_stage import (
    count_stage_deals,
    create_pipeline_stage,
    delete_pipeline_stage,
    get_pipeline_stage,
    get_pipeline_stage_by_name,
    get_pipeline_stage_by_order,
    get_pipeline_stages,
    update_pipeline_stage,
)
from app.schemas.pipeline_stage import (
    PipelineStageCreate,
    PipelineStageList,
    PipelineStageResponse,
    PipelineStageUpdate,
)

router = APIRouter()


def ensure_stage_unique(db: SessionDep, pipeline_id: int, stage_in: PipelineStageCreate | PipelineStageUpdate, stage_id: int | None = None) -> None:
    if stage_in.order is not None:
        duplicate_order = get_pipeline_stage_by_order(db, pipeline_id, stage_in.order)
        if duplicate_order and duplicate_order.id != stage_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A stage with this order already exists")
    if stage_in.name is not None:
        duplicate_name = get_pipeline_stage_by_name(db, pipeline_id, stage_in.name)
        if duplicate_name and duplicate_name.id != stage_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A stage with this name already exists")


def ensure_stage_state_is_valid(is_closed: bool, is_won: bool, is_lost: bool) -> None:
    if is_won and is_lost:
        raise HTTPException(status_code=422, detail="A stage cannot be both won and lost")
    if (is_won or is_lost) and not is_closed:
        raise HTTPException(status_code=422, detail="Won or lost stages must be closed")


@router.post(
    "/pipelines/{pipeline_id}/stages",
    response_model=PipelineStageResponse,
    dependencies=[Depends(require_permission("pipeline_stages.create"))],
)
def create_new_pipeline_stage(
    pipeline_id: int,
    stage_in: PipelineStageCreate,
    db: SessionDep,
    current_user: CurrentActiveUser,
):
    pipeline = get_pipeline(db, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=400, detail="Referenced pipeline does not exist")
    ensure_stage_unique(db, pipeline_id, stage_in)
    return create_pipeline_stage(db, pipeline_id, stage_in)


@router.get(
    "/pipelines/{pipeline_id}/stages",
    response_model=PipelineStageList,
    dependencies=[Depends(require_permission("pipeline_stages.read"))],
)
def read_pipeline_stages(
    pipeline_id: int,
    db: SessionDep,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
):
    pipeline = get_pipeline(db, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    skip = (page - 1) * page_size
    items, total = get_pipeline_stages(db, pipeline_id, skip=skip, limit=page_size)
    pages = (total + page_size - 1) // page_size if total else 0
    return PipelineStageList(items=items, page=page, page_size=page_size, total=total, pages=pages)


@router.get(
    "/pipeline-stages/{stage_id}",
    response_model=PipelineStageResponse,
    dependencies=[Depends(require_permission("pipeline_stages.read"))],
)
def read_pipeline_stage(stage_id: int, db: SessionDep, current_user: CurrentActiveUser):
    stage = get_pipeline_stage(db, stage_id)
    if not stage:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    return stage


@router.put(
    "/pipeline-stages/{stage_id}",
    response_model=PipelineStageResponse,
    dependencies=[Depends(require_permission("pipeline_stages.update"))],
)
def update_existing_pipeline_stage(
    stage_id: int,
    stage_in: PipelineStageUpdate,
    db: SessionDep,
    current_user: CurrentActiveUser,
):
    stage = get_pipeline_stage(db, stage_id)
    if not stage:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    ensure_stage_unique(db, stage.pipeline_id, stage_in, stage_id=stage.id)
    final_is_closed = stage_in.is_closed if stage_in.is_closed is not None else stage.is_closed
    final_is_won = stage_in.is_won if stage_in.is_won is not None else stage.is_won
    final_is_lost = stage_in.is_lost if stage_in.is_lost is not None else stage.is_lost
    ensure_stage_state_is_valid(final_is_closed, final_is_won, final_is_lost)
    return update_pipeline_stage(db, stage, stage_in)


@router.delete("/pipeline-stages/{stage_id}", dependencies=[Depends(require_permission("pipeline_stages.delete"))])
def delete_existing_pipeline_stage(stage_id: int, db: SessionDep, current_user: CurrentActiveUser):
    stage = get_pipeline_stage(db, stage_id)
    if not stage:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if count_stage_deals(db, stage_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pipeline stage has deals and cannot be deleted")
    delete_pipeline_stage(db, stage)
    return {"ok": True}
