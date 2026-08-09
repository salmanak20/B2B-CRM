from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.pagination import PaginatedResponse


class PipelineStageBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    order: int = Field(..., ge=1)
    probability: int = Field(0, ge=0, le=100)
    is_closed: bool = False
    is_won: bool = False
    is_lost: bool = False

    @model_validator(mode="after")
    def validate_closed_state(self):
        if self.is_won and self.is_lost:
            raise ValueError("A stage cannot be both won and lost")
        if (self.is_won or self.is_lost) and not self.is_closed:
            self.is_closed = True
        return self


class PipelineStageCreate(PipelineStageBase):
    pass


class PipelineStageUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    order: Optional[int] = Field(None, ge=1)
    probability: Optional[int] = Field(None, ge=0, le=100)
    is_closed: Optional[bool] = None
    is_won: Optional[bool] = None
    is_lost: Optional[bool] = None

    @model_validator(mode="after")
    def validate_closed_state(self):
        if self.is_won is True and self.is_lost is True:
            raise ValueError("A stage cannot be both won and lost")
        return self


class PipelineStageResponse(PipelineStageBase):
    id: int
    pipeline_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PipelineStageList(PaginatedResponse[PipelineStageResponse]):
    pass
