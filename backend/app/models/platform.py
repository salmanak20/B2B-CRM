"""Independent server-only platform permissions; never a tenant role."""
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.session import Base

class PlatformAdministrator(Base):
    __tablename__='platform_administrators'
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'),primary_key=True)
    auth_user_id: Mapped[str]=mapped_column(String(36),nullable=False)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)

class PlatformAudit(Base):
    __tablename__='platform_audit'
    id: Mapped[int]=mapped_column(primary_key=True)
    actor_id: Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    action: Mapped[str]=mapped_column(String(60),nullable=False)
    target_id: Mapped[int]=mapped_column(nullable=False)
    reason: Mapped[str]=mapped_column(Text,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
