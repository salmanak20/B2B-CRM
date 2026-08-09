from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.schemas.task import TaskCreate, TaskStatus, TaskUpdate


def _db_ready(data: dict) -> dict:
    return {key: value.value if hasattr(value, "value") else value for key, value in data.items()}


def _completed_at_for_status(status: str) -> datetime | None:
    if status == TaskStatus.completed.value:
        return datetime.now(timezone.utc)
    return None


def create_task(db: Session, task_in: TaskCreate, owner_id: int, assigned_to_id: int | None) -> Task:
    data = _db_ready(task_in.model_dump(exclude={"owner_id", "assigned_to_id"}))
    data["owner_id"] = owner_id
    data["assigned_to_id"] = assigned_to_id
    data["completed_at"] = _completed_at_for_status(data.get("status", TaskStatus.pending.value))
    db_task = Task(**data)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def get_task(db: Session, task_id: int) -> Optional[Task]:
    return db.scalars(select(Task).where(Task.id == task_id)).first()


def get_tasks(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    company_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    deal_id: Optional[int] = None,
    due_before: Optional[datetime] = None,
    due_after: Optional[datetime] = None,
    visible_user_id: Optional[int] = None,
) -> Tuple[List[Task], int]:
    query = select(Task)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(or_(Task.title.ilike(search_pattern), Task.description.ilike(search_pattern)))
    if status is not None:
        query = query.where(Task.status == status)
    if priority is not None:
        query = query.where(Task.priority == priority)
    if assigned_to_id is not None:
        query = query.where(Task.assigned_to_id == assigned_to_id)
    if owner_id is not None:
        query = query.where(Task.owner_id == owner_id)
    if company_id is not None:
        query = query.where(Task.company_id == company_id)
    if contact_id is not None:
        query = query.where(Task.contact_id == contact_id)
    if lead_id is not None:
        query = query.where(Task.lead_id == lead_id)
    if deal_id is not None:
        query = query.where(Task.deal_id == deal_id)
    if due_before is not None:
        query = query.where(Task.due_date <= due_before)
    if due_after is not None:
        query = query.where(Task.due_date >= due_after)
    if visible_user_id is not None:
        query = query.where(or_(Task.owner_id == visible_user_id, Task.assigned_to_id == visible_user_id))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(Task.id).offset(skip).limit(limit)).all())
    return items, total


def update_task(db: Session, db_task: Task, task_in: TaskUpdate) -> Task:
    update_data = _db_ready(task_in.model_dump(exclude_unset=True))
    if update_data.get("owner_id") is None:
        update_data.pop("owner_id", None)
    if "status" in update_data:
        update_data["completed_at"] = _completed_at_for_status(update_data["status"])
    for field, value in update_data.items():
        setattr(db_task, field, value)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def update_task_status(db: Session, db_task: Task, status: str) -> Task:
    db_task.status = status
    db_task.completed_at = _completed_at_for_status(status)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def update_task_assignee(db: Session, db_task: Task, assigned_to_id: int | None) -> Task:
    db_task.assigned_to_id = assigned_to_id
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def delete_task(db: Session, db_task: Task) -> None:
    db.delete(db_task)
    db.commit()
