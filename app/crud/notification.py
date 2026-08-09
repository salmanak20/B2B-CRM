from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.notification import Notification
from app.schemas.notification import NotificationCreate, NotificationUpdate
from typing import List, Optional

def get_notifications(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[Notification]:
    return db.query(Notification).filter(Notification.user_id == user_id).order_by(desc(Notification.created_at)).offset(skip).limit(limit).all()

def get_notification(db: Session, notification_id: int) -> Optional[Notification]:
    return db.query(Notification).filter(Notification.id == notification_id).first()

def create_notification(db: Session, obj_in: NotificationCreate) -> Notification:
    db_obj = Notification(
        title=obj_in.title,
        message=obj_in.message,
        notification_type=obj_in.notification_type,
        user_id=obj_in.user_id,
        related_entity=obj_in.related_entity,
        related_entity_id=obj_in.related_entity_id,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def mark_as_read(db: Session, notification: Notification) -> Notification:
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification

def mark_all_as_read(db: Session, user_id: int) -> int:
    result = db.query(Notification).filter(
        Notification.user_id == user_id, 
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return result

def delete_notification(db: Session, notification: Notification) -> None:
    db.delete(notification)
    db.commit()
