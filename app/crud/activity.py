from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.schemas.activity import ActivityCreate, ActivityUpdate


def _db_ready(data: dict) -> dict:
    return {key: value.value if hasattr(value, "value") else value for key, value in data.items()}


def create_activity(db: Session, activity_in: ActivityCreate, user_id: int) -> Activity:
    data = _db_ready(activity_in.model_dump(exclude={"user_id"}))
    if data.get("occurred_at") is None:
        data["occurred_at"] = datetime.now(timezone.utc)
    db_activity = Activity(**data, user_id=user_id)
    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    return db_activity


def get_activity(db: Session, activity_id: int) -> Optional[Activity]:
    return db.scalars(select(Activity).where(Activity.id == activity_id)).first()


def get_activities(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    type: Optional[str] = None,
    user_id: Optional[int] = None,
    company_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    deal_id: Optional[int] = None,
    occurred_before: Optional[datetime] = None,
    occurred_after: Optional[datetime] = None,
    visible_user_id: Optional[int] = None,
) -> Tuple[List[Activity], int]:
    query = select(Activity)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(or_(Activity.subject.ilike(search_pattern), Activity.description.ilike(search_pattern)))
    if type is not None:
        query = query.where(Activity.type == type)
    if user_id is not None:
        query = query.where(Activity.user_id == user_id)
    if company_id is not None:
        query = query.where(Activity.company_id == company_id)
    if contact_id is not None:
        query = query.where(Activity.contact_id == contact_id)
    if lead_id is not None:
        query = query.where(Activity.lead_id == lead_id)
    if deal_id is not None:
        query = query.where(Activity.deal_id == deal_id)
    if occurred_before is not None:
        query = query.where(Activity.occurred_at <= occurred_before)
    if occurred_after is not None:
        query = query.where(Activity.occurred_at >= occurred_after)
    if visible_user_id is not None:
        query = query.where(Activity.user_id == visible_user_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(Activity.id).offset(skip).limit(limit)).all())
    return items, total


def update_activity(db: Session, db_activity: Activity, activity_in: ActivityUpdate) -> Activity:
    update_data = _db_ready(activity_in.model_dump(exclude_unset=True))
    if update_data.get("user_id") is None:
        update_data.pop("user_id", None)
    for field, value in update_data.items():
        setattr(db_activity, field, value)
    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    return db_activity


def delete_activity(db: Session, db_activity: Activity) -> None:
    db.delete(db_activity)
    db.commit()
