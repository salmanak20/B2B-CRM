from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from datetime import timedelta

from app.api.deps import SessionDep, CurrentActiveUser
from app.core.security import verify_password, create_access_token
from app.core.config import settings
from app.crud.user import get_user_by_email, create_user
from app.schemas.auth import Token, UserRegister
from app.schemas.user import UserResponse
from app.models.role import Role

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse)
def register(user_in: UserRegister, db: SessionDep) -> Any:
    user = get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The user with this email already exists in the system.",
        )
    # Get default role "sales_rep"
    role = db.scalars(select(Role).where(Role.name == "sales_rep")).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Default role not found. Please seed the database.")
    
    user = create_user(db, user_in=user_in, role_id=role.id)
    return user

@router.post("/login", response_model=Token)
def login(db: SessionDep, form_data: OAuth2PasswordRequestForm = Depends()) -> Any:
    # form_data.username is the email in OAuth2
    user = get_user_by_email(db, email=form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }

@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: CurrentActiveUser) -> Any:
    return current_user
