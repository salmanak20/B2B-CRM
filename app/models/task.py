from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("priority IN ('low', 'medium', 'high', 'urgent')", name="ck_tasks_priority_values"),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')",
            name="ck_tasks_status_values",
        ),
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status != 'completed' AND completed_at IS NULL)",
            name="ck_tasks_completion_state",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True, nullable=True)
    contact_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), index=True, nullable=True)
    lead_id: Mapped[Optional[int]] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"), index=True, nullable=True)
    deal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"), index=True, nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), index=True, default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(20), index=True, default="pending", nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    owner: Mapped["User"] = relationship(foreign_keys=[owner_id], back_populates="owned_tasks")
    assigned_to: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_to_id], back_populates="assigned_tasks")
    company: Mapped[Optional["Company"]] = relationship(back_populates="tasks")
    contact: Mapped[Optional["Contact"]] = relationship(back_populates="tasks")
    lead: Mapped[Optional["Lead"]] = relationship(back_populates="tasks")
    deal: Mapped[Optional["Deal"]] = relationship(back_populates="tasks")
