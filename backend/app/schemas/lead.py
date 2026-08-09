from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from app.schemas.pagination import PaginatedResponse
from enum import Enum

class LeadStatus(str, Enum):
    new = "new"
    contacted = "contacted"
    qualified = "qualified"
    nurturing = "nurturing"
    unqualified = "unqualified"
    converted = "converted"
    lost = "lost"

class LeadSource(str, Enum):
    website = "website"
    referral = "referral"
    email = "email"
    phone = "phone"
    social_media = "social_media"
    advertisement = "advertisement"
    cold_call = "cold_call"
    event = "event"
    other = "other"

class LeadBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    company_id: Optional[int] = None
    contact_id: Optional[int] = None
    source: Optional[LeadSource] = None
    status: LeadStatus
    estimated_value: Optional[float] = Field(None, ge=0)
    lead_score: Optional[int] = Field(0, ge=0, le=100)

class LeadCreate(LeadBase):
    owner_id: Optional[int] = None

class LeadUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    company_id: Optional[int] = None
    contact_id: Optional[int] = None
    source: Optional[LeadSource] = None
    status: Optional[LeadStatus] = None
    estimated_value: Optional[float] = Field(None, ge=0)
    lead_score: Optional[int] = Field(None, ge=0, le=100)
    owner_id: Optional[int] = None

class LeadResponse(LeadBase):
    id: int
    owner_id: int
    name: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class LeadList(PaginatedResponse[LeadResponse]):
    pass
