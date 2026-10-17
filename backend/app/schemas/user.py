from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional
from datetime import datetime

class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True)
    name: Optional[str] = Field(None,min_length=1,max_length=100)
    email: Optional[EmailStr] = None
    preferences: Optional[dict] = None

class UserUpdateAdmin(UserUpdate):
    role_id: Optional[int] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    organization_id: int | None = None
    organization_role: str | None = None
    id: int
    role: RoleResponse
    is_active: bool
    created_at: datetime
    preferences: dict = Field(default_factory=dict)
    auth_linked: bool = False
    
    model_config = ConfigDict(from_attributes=True)
