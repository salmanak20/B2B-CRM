from pydantic import BaseModel, Field, ConfigDict, EmailStr, HttpUrl
from typing import Optional
from datetime import datetime
from decimal import Decimal
from app.schemas.pagination import PaginatedResponse

class CompanyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    website: Optional[HttpUrl] = None
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    size: Optional[str] = Field(None, max_length=50)
    revenue: Optional[Decimal] = Field(None, ge=0)

class CompanyCreate(CompanyBase):
    owner_id: Optional[int] = None

class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    website: Optional[HttpUrl] = None
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    size: Optional[str] = Field(None, max_length=50)
    revenue: Optional[Decimal] = Field(None, ge=0)
    owner_id: Optional[int] = None

class CompanyResponse(CompanyBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class CompanyList(PaginatedResponse[CompanyResponse]):
    pass
