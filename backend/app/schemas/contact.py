from app.schemas.related import NamedUser, NamedCompany, NamedContact
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime
from app.schemas.pagination import PaginatedResponse

class ContactBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False, extra="forbid")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    job_title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    company_id: int

class ContactCreate(ContactBase):
    owner_id: Optional[int] = None

class ContactUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False, extra="forbid")
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    job_title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    company_id: Optional[int] = None
    owner_id: Optional[int] = None

class ContactResponse(ContactBase):
    id: int
    owner_id: int
    company: NamedCompany | None = None
    owner: NamedUser | None = None
    name: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ContactList(PaginatedResponse[ContactResponse]):
    pass
