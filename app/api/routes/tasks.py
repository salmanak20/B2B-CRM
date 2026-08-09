from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.crm_validation import validate_crm_relationships
from app.api.deps import CurrentActiveUser, SessionDep, require_permission
from app.api.ownership import can_manage_all_crm_records, can_read_crm_record, resolve_owner_id
from app.crud.task import (
    create_task,
    delete_task,
    get_task,
    get_tasks,
    update_task,
    update_task_assignee,
    update_task_status,
)
from app.crud.user import get_user_by_id
from app.models.task import Task
from app.models.user import User
from app.schemas.task import (
    TaskAssigneeUpdate,
    TaskCreate,
    TaskList,
    TaskPriority,
    TaskResponse,
    TaskStatus,
    TaskStatusUpdate,
    TaskUpdate,
)
from app.crud.audit_log import log_event

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


def can_read_task(task: Task, current_user: User) -> bool:
    return can_read_crm_record(task.owner_id, current_user) or task.assigned_to_id == current_user.id


def ensure_can_read_task(task: Task, current_user: User) -> None:
    if not can_read_task(task, current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions to access this task")


def ensure_can_modify_task(task: Task, current_user: User) -> None:
    if can_manage_all_crm_records(current_user):
        return
    if task.owner_id != current_user.id and task.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions to modify this task")


def resolve_assigned_to_id(db: SessionDep, current_user: CurrentActiveUser, requested_user_id: int | None) -> int | None:
    if requested_user_id is None:
        return None
    user = get_user_by_id(db, requested_user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Assigned user does not exist")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Assigned user is inactive")
    if requested_user_id != current_user.id and not can_manage_all_crm_records(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions to assign tasks to this user")
    return requested_user_id


@router.post("", response_model=TaskResponse, dependencies=[Depends(require_permission("tasks.create"))])
def create_new_task(task_in: TaskCreate, db: SessionDep, current_user: CurrentActiveUser):
    validate_crm_relationships(db, current_user, task_in.company_id, task_in.contact_id, task_in.lead_id, task_in.deal_id)
    owner_id = resolve_owner_id(db, current_user, task_in.owner_id)
    assigned_to_id = resolve_assigned_to_id(db, current_user, task_in.assigned_to_id)
    task = create_task(db, task_in, owner_id, assigned_to_id)
    log_event(db, action="Task Created", user_id=current_user.id, entity="Task", entity_id=task.id, description=f"Created task {task.title}")
    return task


@router.get("", response_model=TaskList, dependencies=[Depends(require_permission("tasks.read"))])
def read_tasks(
    db: SessionDep,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[TaskStatus] = None,
    priority: Optional[TaskPriority] = None,
    assigned_to_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    company_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    deal_id: Optional[int] = None,
    due_before: Optional[str] = None,
    due_after: Optional[str] = None,
):
    if owner_id is not None and not can_read_crm_record(owner_id, current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions to filter by this owner")
    if assigned_to_id is not None and assigned_to_id != current_user.id and not can_manage_all_crm_records(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions to filter by this assignee")
    skip = (page - 1) * page_size
    visible_user_id = None if current_user.role.name in {"admin", "administrator", "sales_manager", "viewer"} else current_user.id
    items, total = get_tasks(
        db,
        skip=skip,
        limit=page_size,
        search=search,
        status=status,
        priority=priority,
        assigned_to_id=assigned_to_id,
        owner_id=owner_id,
        company_id=company_id,
        contact_id=contact_id,
        lead_id=lead_id,
        deal_id=deal_id,
        due_before=parse_datetime_filter(due_before, end_of_day=True),
        due_after=parse_datetime_filter(due_after),
        visible_user_id=visible_user_id,
    )
    pages = (total + page_size - 1) // page_size if total else 0
    return TaskList(items=items, page=page, page_size=page_size, total=total, pages=pages)


@router.get("/{task_id}", response_model=TaskResponse, dependencies=[Depends(require_permission("tasks.read"))])
def read_task(task_id: int, db: SessionDep, current_user: CurrentActiveUser):
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    ensure_can_read_task(task, current_user)
    return task


@router.put("/{task_id}", response_model=TaskResponse, dependencies=[Depends(require_permission("tasks.update"))])
def update_existing_task(task_id: int, task_in: TaskUpdate, db: SessionDep, current_user: CurrentActiveUser):
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    ensure_can_modify_task(task, current_user)
    update_data = task_in.model_dump(exclude_unset=True)
    validate_crm_relationships(
        db,
        current_user,
        update_data.get("company_id", task.company_id),
        update_data.get("contact_id", task.contact_id),
        update_data.get("lead_id", task.lead_id),
        update_data.get("deal_id", task.deal_id),
    )
    if task_in.owner_id is not None:
        task_in.owner_id = resolve_owner_id(db, current_user, task_in.owner_id)
    if "assigned_to_id" in task_in.model_fields_set:
        task_in.assigned_to_id = resolve_assigned_to_id(db, current_user, task_in.assigned_to_id)
    updated_task = update_task(db, task, task_in)
    log_event(db, action="Task Updated", user_id=current_user.id, entity="Task", entity_id=updated_task.id, description=f"Updated task {updated_task.title}")
    return updated_task


@router.patch("/{task_id}/status", response_model=TaskResponse, dependencies=[Depends(require_permission("tasks.update"))])
def patch_task_status(task_id: int, status_in: TaskStatusUpdate, db: SessionDep, current_user: CurrentActiveUser):
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    ensure_can_modify_task(task, current_user)
    updated_task = update_task_status(db, task, status_in.status.value)
    
    action = "Task Completed" if status_in.status.value == "completed" else "Task Status Changed"
    log_event(db, action=action, user_id=current_user.id, entity="Task", entity_id=updated_task.id, description=f"Task {updated_task.title} status changed to {status_in.status.value}")
    
    return updated_task


@router.patch("/{task_id}/assignee", response_model=TaskResponse, dependencies=[Depends(require_permission("tasks.update"))])
def patch_task_assignee(task_id: int, assignee_in: TaskAssigneeUpdate, db: SessionDep, current_user: CurrentActiveUser):
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    ensure_can_modify_task(task, current_user)
    assigned_to_id = resolve_assigned_to_id(db, current_user, assignee_in.assigned_to_id)
    updated_task = update_task_assignee(db, task, assigned_to_id)
    log_event(db, action="Task Assigned", user_id=current_user.id, entity="Task", entity_id=updated_task.id, description=f"Task {updated_task.title} assigned to user {assigned_to_id}")
    return updated_task


@router.delete("/{task_id}", dependencies=[Depends(require_permission("tasks.delete"))])
def delete_existing_task(task_id: int, db: SessionDep, current_user: CurrentActiveUser):
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    ensure_can_modify_task(task, current_user)
    delete_task(db, task)
    return {"ok": True}
