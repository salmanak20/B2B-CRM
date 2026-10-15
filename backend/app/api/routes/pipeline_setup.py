from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.api.deps import SessionDep, CurrentActiveUser, require_permission
from app.schemas.pipeline import PipelineCreate
from app.schemas.pipeline_stage import PipelineStageCreate
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.crud.audit_log import log_event
from sqlalchemy import select, func
router=APIRouter()
class PipelineSetup(BaseModel):
    pipeline:PipelineCreate
    stages:list[PipelineStageCreate]=Field(min_length=1,max_length=20)

@router.post('/pipeline-setup',dependencies=[Depends(require_permission('pipelines.create'))])
def setup(body:PipelineSetup,db:SessionDep,current_user:CurrentActiveUser):
    if len({s.name.casefold() for s in body.stages})!=len(body.stages) or len({s.order for s in body.stages})!=len(body.stages):
        raise HTTPException(422,'Stage names and order values must be unique')
    if db.scalar(select(Pipeline).where(func.lower(Pipeline.name)==body.pipeline.name.casefold())):
        raise HTTPException(409,'A pipeline with this name already exists')
    pipeline=Pipeline(**body.pipeline.model_dump());db.add(pipeline);db.flush()
    for stage in body.stages:db.add(PipelineStage(**stage.model_dump(),pipeline_id=pipeline.id))
    db.commit();db.refresh(pipeline)
    log_event(db,'Pipeline Created',current_user.id,'Pipeline',pipeline.id,pipeline.name)
    return {'id':pipeline.id,'name':pipeline.name}
