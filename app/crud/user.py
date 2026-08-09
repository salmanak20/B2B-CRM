from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserUpdateAdmin
from app.core.security import hash_password
from typing import Optional, List
from sqlalchemy import select

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.scalars(select(User).where(User.id == user_id)).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.scalars(select(User).where(User.email == email)).first()

def create_user(db: Session, user_in: UserCreate, role_id: int) -> User:
    db_user = User(
        name=user_in.name,
        email=user_in.email,
        password_hash=hash_password(user_in.password),
        role_id=role_id,
        is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, db_user: User, user_in: UserUpdate | UserUpdateAdmin) -> User:
    update_data = user_in.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_user, field, value)
        
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return list(db.scalars(select(User).offset(skip).limit(limit)).all())
