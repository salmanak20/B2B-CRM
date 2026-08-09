from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.deal import DealResponse
from app.schemas.pagination import PaginatedResponse
from app.schemas.pipeline_stage import PipelineStageResponse


class PipelineBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    is_default: bool = False
    is_active: bool = True


class PipelineCreate(PipelineBase):
    pass


class PipelineUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class PipelineResponse(PipelineBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PipelineList(PaginatedResponse[PipelineResponse]):
    pass


class PipelineBoardStage(PipelineStageResponse):
    deals: List[DealResponse]


class PipelineBoardResponse(PipelineResponse):
    stages: List[PipelineBoardStage]
