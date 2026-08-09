from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentActiveUser, SessionDep, require_permission
from app.api.ownership import can_read_crm_record
from app.crud.pipeline import (
    count_pipeline_deals,
    count_pipeline_stages,
    create_pipeline,
    delete_pipeline,
    get_pipeline,
    get_pipeline_board,
    get_pipeline_by_name,
    get_pipelines,
    update_pipeline,
)
from app.schemas.pipeline import PipelineBoardResponse, PipelineCreate, PipelineList, PipelineResponse, PipelineUpdate

router = APIRouter()


@router.post("", response_model=PipelineResponse, dependencies=[Depends(require_permission("pipelines.create"))])
def create_new_pipeline(pipeline_in: PipelineCreate, db: SessionDep, current_user: CurrentActiveUser):
    if get_pipeline_by_name(db, pipeline_in.name):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A pipeline with this name already exists")
    return create_pipeline(db, pipeline_in)


@router.get("", response_model=PipelineList, dependencies=[Depends(require_permission("pipelines.read"))])
def read_pipelines(
    db: SessionDep,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    skip = (page - 1) * page_size
    items, total = get_pipelines(db, skip=skip, limit=page_size, search=search, is_active=is_active)
    pages = (total + page_size - 1) // page_size if total else 0
    return PipelineList(items=items, page=page, page_size=page_size, total=total, pages=pages)


@router.get("/{pipeline_id}", response_model=PipelineResponse, dependencies=[Depends(require_permission("pipelines.read"))])
def read_pipeline(pipeline_id: int, db: SessionDep, current_user: CurrentActiveUser):
    pipeline = get_pipeline(db, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.get("/{pipeline_id}/board", response_model=PipelineBoardResponse, dependencies=[Depends(require_permission("pipelines.read"))])
def read_pipeline_board(pipeline_id: int, db: SessionDep, current_user: CurrentActiveUser):
    pipeline = get_pipeline_board(db, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    stages = []
    for stage in sorted(pipeline.stages, key=lambda item: (item.order, item.id)):
        visible_deals = [
            deal
            for deal in sorted(stage.deals, key=lambda item: item.id)
            if can_read_crm_record(deal.owner_id, current_user)
        ]
        stages.append(
            {
                "id": stage.id,
                "pipeline_id": stage.pipeline_id,
                "name": stage.name,
                "order": stage.order,
                "probability": stage.probability,
                "is_closed": stage.is_closed,
                "is_won": stage.is_won,
                "is_lost": stage.is_lost,
                "created_at": stage.created_at,
                "updated_at": stage.updated_at,
                "deals": visible_deals,
            }
        )

    return {
        "id": pipeline.id,
        "name": pipeline.name,
        "description": pipeline.description,
        "is_default": pipeline.is_default,
        "is_active": pipeline.is_active,
        "created_at": pipeline.created_at,
        "updated_at": pipeline.updated_at,
        "stages": stages,
    }


@router.put("/{pipeline_id}", response_model=PipelineResponse, dependencies=[Depends(require_permission("pipelines.update"))])
def update_existing_pipeline(pipeline_id: int, pipeline_in: PipelineUpdate, db: SessionDep, current_user: CurrentActiveUser):
    pipeline = get_pipeline(db, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if pipeline_in.name is not None:
        duplicate = get_pipeline_by_name(db, pipeline_in.name)
        if duplicate and duplicate.id != pipeline.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A pipeline with this name already exists")
    return update_pipeline(db, pipeline, pipeline_in)


@router.delete("/{pipeline_id}", dependencies=[Depends(require_permission("pipelines.delete"))])
def delete_existing_pipeline(pipeline_id: int, db: SessionDep, current_user: CurrentActiveUser):
    pipeline = get_pipeline(db, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if count_pipeline_deals(db, pipeline_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pipeline has deals and cannot be deleted")
    if count_pipeline_stages(db, pipeline_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pipeline has stages and cannot be deleted")
    delete_pipeline(db, pipeline)
    return {"ok": True}
