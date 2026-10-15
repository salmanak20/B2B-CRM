from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRegister(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str

    @field_validator("name")
    @classmethod
    def meaningful_name(cls,value):
        if not value.strip():
            raise ValueError("Name is required")
        return value.strip()

    @field_validator("password")
    @classmethod
    def secure_password(cls,value):
        if len(value)<12 or len(value.encode('utf-8'))>72:
            raise ValueError("Use at least 12 characters and no more than 72 UTF-8 bytes")
        return value

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenPayload(BaseModel):
    sub: Optional[str] = None
