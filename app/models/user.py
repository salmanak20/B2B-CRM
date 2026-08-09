from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, ForeignKey, DateTime
from sqlalchemy.sql import func
from datetime import datetime
from typing import List
from app.db.session import Base

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    role: Mapped["Role"] = relationship(back_populates="users")
    
    companies: Mapped[List["Company"]] = relationship(back_populates="owner")
    contacts: Mapped[List["Contact"]] = relationship(back_populates="owner")
    leads: Mapped[List["Lead"]] = relationship(back_populates="owner")
    deals: Mapped[List["Deal"]] = relationship(back_populates="owner")
    owned_tasks: Mapped[List["Task"]] = relationship(foreign_keys="Task.owner_id", back_populates="owner")
    assigned_tasks: Mapped[List["Task"]] = relationship(foreign_keys="Task.assigned_to_id", back_populates="assigned_to")
    activities: Mapped[List["Activity"]] = relationship(back_populates="user")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship(back_populates="user")
