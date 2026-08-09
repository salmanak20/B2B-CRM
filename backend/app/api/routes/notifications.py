from fastapi import APIRouter, HTTPException, status
from typing import List
from app.api.deps import SessionDep, CurrentActiveUser
from app.schemas.notification import NotificationResponse
from app.crud import notification as crud_notification

router = APIRouter()

@router.get("/", response_model=List[NotificationResponse])
def get_notifications(
    db: SessionDep,
    current_user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 100
):
    return crud_notification.get_notifications(db=db, user_id=current_user.id, skip=skip, limit=limit)

@router.patch("/read-all", response_model=dict)
def mark_all_as_read(
    db: SessionDep,
    current_user: CurrentActiveUser,
):
    crud_notification.mark_all_as_read(db=db, user_id=current_user.id)
    return {"message": "All notifications marked as read"}

@router.get("/{id}", response_model=NotificationResponse)
def get_notification(
    id: int,
    db: SessionDep,
    current_user: CurrentActiveUser,
):
    notification = crud_notification.get_notification(db=db, notification_id=id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return notification

@router.patch("/{id}/read", response_model=NotificationResponse)
def mark_as_read(
    id: int,
    db: SessionDep,
    current_user: CurrentActiveUser,
):
    notification = crud_notification.get_notification(db=db, notification_id=id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return crud_notification.mark_as_read(db=db, notification=notification)

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    id: int,
    db: SessionDep,
    current_user: CurrentActiveUser,
):
    notification = crud_notification.get_notification(db=db, notification_id=id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    crud_notification.delete_notification(db=db, notification=notification)
