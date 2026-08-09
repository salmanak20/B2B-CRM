from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.deps import SessionDep, CurrentActiveUser, require_role
from app.schemas.user import UserResponse, UserUpdate, UserUpdateAdmin
from app.crud.user import update_user, get_user_by_id, get_users

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserResponse)
def read_user_me(current_user: CurrentActiveUser) -> Any:
    return current_user

@router.put("/me", response_model=UserResponse)
def update_user_me(
    user_in: UserUpdate, current_user: CurrentActiveUser, db: SessionDep
) -> Any:
    return update_user(db, db_user=current_user, user_in=user_in)

# Administrator endpoints
@router.get("", response_model=List[UserResponse], dependencies=[Depends(require_role(["admin"]))])
def read_users(db: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    return get_users(db, skip=skip, limit=limit)

@router.get("/{user_id}", response_model=UserResponse, dependencies=[Depends(require_role(["admin"]))])
def read_user_by_id(user_id: int, db: SessionDep) -> Any:
    user = get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}", response_model=UserResponse, dependencies=[Depends(require_role(["admin"]))])
def update_user_by_id(
    user_id: int, user_in: UserUpdateAdmin, db: SessionDep
) -> Any:
    user = get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return update_user(db, db_user=user, user_in=user_in)

@router.patch("/{user_id}/status", response_model=UserResponse, dependencies=[Depends(require_role(["admin"]))])
def change_user_status(
    user_id: int, is_active: bool, db: SessionDep
) -> Any:
    user = get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = UserUpdateAdmin(is_active=is_active)
    return update_user(db, db_user=user, user_in=update_data)
