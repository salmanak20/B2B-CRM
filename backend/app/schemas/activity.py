from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pagination import PaginatedResponse


class ActivityType(str, Enum):
    call = "call"
    email = "email"
    meeting = "meeting"
    note = "note"
    follow_up = "follow_up"


class ActivityBase(BaseModel):
    type: ActivityType
    subject: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    company_id: Optional[int] = None
    contact_id: Optional[int] = None
    lead_id: Optional[int] = None
    deal_id: Optional[int] = None
    occurred_at: Optional[datetime] = None


class ActivityCreate(ActivityBase):
    user_id: Optional[int] = None


class ActivityUpdate(BaseModel):
    type: Optional[ActivityType] = None
    subject: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    user_id: Optional[int] = None
    company_id: Optional[int] = None
    contact_id: Optional[int] = None
    lead_id: Optional[int] = None
    deal_id: Optional[int] = None
    occurred_at: Optional[datetime] = None


class ActivityResponse(ActivityBase):
    id: int
    user_id: int
    occurred_at: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ActivityList(PaginatedResponse[ActivityResponse]):
    pass
