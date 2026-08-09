from pydantic import BaseModel, EmailStr, ConfigDict
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
    name: Optional[str] = None
    email: Optional[EmailStr] = None

class UserUpdateAdmin(UserUpdate):
    role_id: Optional[int] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    role: RoleResponse
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
