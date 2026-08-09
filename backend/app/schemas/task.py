from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pagination import PaginatedResponse


class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class TaskStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    assigned_to_id: Optional[int] = None
    company_id: Optional[int] = None
    contact_id: Optional[int] = None
    lead_id: Optional[int] = None
    deal_id: Optional[int] = None
    due_date: Optional[datetime] = None
    priority: TaskPriority = TaskPriority.medium
    status: TaskStatus = TaskStatus.pending


class TaskCreate(TaskBase):
    owner_id: Optional[int] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    owner_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    company_id: Optional[int] = None
    contact_id: Optional[int] = None
    lead_id: Optional[int] = None
    deal_id: Optional[int] = None
    due_date: Optional[datetime] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskAssigneeUpdate(BaseModel):
    assigned_to_id: Optional[int] = None


class TaskResponse(TaskBase):
    id: int
    owner_id: int
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TaskList(PaginatedResponse[TaskResponse]):
    pass
