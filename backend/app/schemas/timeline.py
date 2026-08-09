from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.activity import ActivityType
from app.schemas.task import TaskPriority, TaskStatus


class TimelineItem(BaseModel):
    type: str
    id: int
    title: str
    description: Optional[str] = None
    occurred_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    activity_type: Optional[ActivityType] = None
    task_status: Optional[TaskStatus] = None
    task_priority: Optional[TaskPriority] = None


class TimelineResponse(BaseModel):
    items: list[TimelineItem]
    page: int
    page_size: int
    total: int
    pages: int
