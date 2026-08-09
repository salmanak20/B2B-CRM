from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pagination import PaginatedResponse


class DealStatus(str, Enum):
    open = "open"
    won = "won"
    lost = "lost"


class DealBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    company_id: Optional[int] = None
    contact_id: Optional[int] = None
    lead_id: Optional[int] = None
    pipeline_id: int
    stage_id: int
    value: Decimal = Field(Decimal("0"), ge=0)
    probability: int = Field(0, ge=0, le=100)
    expected_close_date: Optional[date] = None
    status: DealStatus = DealStatus.open


class DealCreate(DealBase):
    owner_id: Optional[int] = None


class DealUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    owner_id: Optional[int] = None
    company_id: Optional[int] = None
    contact_id: Optional[int] = None
    lead_id: Optional[int] = None
    pipeline_id: Optional[int] = None
    stage_id: Optional[int] = None
    value: Optional[Decimal] = Field(None, ge=0)
    probability: Optional[int] = Field(None, ge=0, le=100)
    expected_close_date: Optional[date] = None
    status: Optional[DealStatus] = None


class DealStageUpdate(BaseModel):
    stage_id: int


class DealResponse(DealBase):
    id: int
    owner_id: int
    status: DealStatus
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DealList(PaginatedResponse[DealResponse]):
    pass
