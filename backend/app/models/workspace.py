from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, JSON, Numeric, ForeignKey, DateTime, UniqueConstraint, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.session import Base

class WorkspaceSettings(Base):
    __tablename__="workspace_settings"
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(100),default="CRM Pro")
    timezone: Mapped[str]=mapped_column(String(100),default="UTC")
    currency: Mapped[str]=mapped_column(String(3),default="USD")

class WorkflowRule(Base):
    __tablename__="workflow_rules"
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(100))
    owner_id: Mapped[int]=mapped_column(ForeignKey("users.id"))
    trigger_status: Mapped[str]=mapped_column(String(30),default="qualified")
    min_value: Mapped[Decimal]=mapped_column(Numeric(15,2),default=0)
    assigned_to_id: Mapped[int | None]=mapped_column(ForeignKey("users.id"),nullable=True)
    task_title: Mapped[str]=mapped_column(String(255))
    enabled: Mapped[bool]=mapped_column(Boolean,default=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class WorkflowRun(Base):
    __tablename__="workflow_runs"
    __table_args__=(UniqueConstraint("rule_id","lead_id",name="uq_workflow_lead_once"),)
    id: Mapped[int]=mapped_column(primary_key=True)
    rule_id: Mapped[int]=mapped_column(ForeignKey("workflow_rules.id",ondelete="CASCADE"))
    lead_id: Mapped[int]=mapped_column(ForeignKey("leads.id",ondelete="CASCADE"))
    task_id: Mapped[int | None]=mapped_column(ForeignKey("tasks.id",ondelete="SET NULL"),nullable=True)

class Attachment(Base):
    __tablename__="attachments"
    id: Mapped[int]=mapped_column(primary_key=True)
    entity: Mapped[str]=mapped_column(String(30),index=True)
    entity_id: Mapped[int]=mapped_column(index=True)
    uploaded_by: Mapped[int]=mapped_column(ForeignKey("users.id"))
    name: Mapped[str]=mapped_column(String(255))
    storage_path: Mapped[str]=mapped_column(Text,unique=True)
    content_type: Mapped[str]=mapped_column(String(100))
    size: Mapped[int]=mapped_column()
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
