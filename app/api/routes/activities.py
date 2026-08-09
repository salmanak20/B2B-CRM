from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.crm_validation import validate_crm_relationships
from app.api.deps import CurrentActiveUser, SessionDep, require_permission
from app.api.ownership import can_manage_all_crm_records, can_read_crm_record
from app.crud.activity import create_activity, delete_activity, get_activities, get_activity, update_activity
from app.crud.user import get_user_by_id
from app.models.activity import Activity
from app.models.user import User
from app.schemas.activity import ActivityCreate, ActivityList, ActivityResponse, ActivityType, ActivityUpdate

router = APIRouter()


def parse_datetime_filter(value: str | None, end_of_day: bool = False) -> datetime | None:
    if value is None:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date filter")
        return datetime.combine(parsed_date, time.max if end_of_day else time.min)


def can_read_activity(activity: Activity, current_user: User) -> bool:
    return can_read_crm_record(activity.user_id, current_user)


def ensure_can_read_activity(activity: Activity, current_user: User) -> None:
    if not can_read_activity(activity, current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions to access this activity")


def ensure_can_modify_activity(activity: Activity, current_user: User) -> None:
    if can_manage_all_crm_records(current_user):
        return
    if activity.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions to modify this activity")


def resolve_activity_user_id(db: SessionDep, current_user: CurrentActiveUser, requested_user_id: int | None) -> int:
    if requested_user_id is None or requested_user_id == current_user.id:
        return current_user.id
    if not can_manage_all_crm_records(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions to create activity for this user")
    user = get_user_by_id(db, requested_user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Activity user does not exist")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Activity user is inactive")
    return requested_user_id


@router.post("", response_model=ActivityResponse, dependencies=[Depends(require_permission("activities.create"))])
def create_new_activity(activity_in: ActivityCreate, db: SessionDep, current_user: CurrentActiveUser):
    validate_crm_relationships(
        db, current_user, activity_in.company_id, activity_in.contact_id, activity_in.lead_id, activity_in.deal_id
    )
    user_id = resolve_activity_user_id(db, current_user, activity_in.user_id)
    return create_activity(db, activity_in, user_id)


@router.get("", response_model=ActivityList, dependencies=[Depends(require_permission("activities.read"))])
def read_activities(
    db: SessionDep,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    type: Optional[ActivityType] = None,
    user_id: Optional[int] = None,
    company_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    deal_id: Optional[int] = None,
    occurred_before: Optional[str] = None,
    occurred_after: Optional[str] = None,
):
    if user_id is not None and not can_read_crm_record(user_id, current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions to filter by this user")
    skip = (page - 1) * page_size
    visible_user_id = None if current_user.role.name in {"admin", "administrator", "sales_manager", "viewer"} else current_user.id
    items, total = get_activities(
        db,
        skip=skip,
        limit=page_size,
        search=search,
        type=type,
        user_id=user_id,
        company_id=company_id,
        contact_id=contact_id,
        lead_id=lead_id,
        deal_id=deal_id,
        occurred_before=parse_datetime_filter(occurred_before, end_of_day=True),
        occurred_after=parse_datetime_filter(occurred_after),
        visible_user_id=visible_user_id,
    )
    pages = (total + page_size - 1) // page_size if total else 0
    return ActivityList(items=items, page=page, page_size=page_size, total=total, pages=pages)


@router.get("/{activity_id}", response_model=ActivityResponse, dependencies=[Depends(require_permission("activities.read"))])
def read_activity(activity_id: int, db: SessionDep, current_user: CurrentActiveUser):
    activity = get_activity(db, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    ensure_can_read_activity(activity, current_user)
    return activity


@router.put("/{activity_id}", response_model=ActivityResponse, dependencies=[Depends(require_permission("activities.update"))])
def update_existing_activity(
    activity_id: int, activity_in: ActivityUpdate, db: SessionDep, current_user: CurrentActiveUser
):
    activity = get_activity(db, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    ensure_can_modify_activity(activity, current_user)
    update_data = activity_in.model_dump(exclude_unset=True)
    validate_crm_relationships(
        db,
        current_user,
        update_data.get("company_id", activity.company_id),
        update_data.get("contact_id", activity.contact_id),
        update_data.get("lead_id", activity.lead_id),
        update_data.get("deal_id", activity.deal_id),
    )
    if "user_id" in activity_in.model_fields_set:
        activity_in.user_id = resolve_activity_user_id(db, current_user, activity_in.user_id)
    return update_activity(db, activity, activity_in)


@router.delete("/{activity_id}", dependencies=[Depends(require_permission("activities.delete"))])
def delete_existing_activity(activity_id: int, db: SessionDep, current_user: CurrentActiveUser):
    activity = get_activity(db, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    ensure_can_modify_activity(activity, current_user)
    delete_activity(db, activity)
    return {"ok": True}
