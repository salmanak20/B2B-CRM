from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from datetime import datetime
from typing import List, Optional
from app.db.session import Base

class Contact(Base):
    __tablename__ = "contacts"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    company: Mapped["Company"] = relationship(back_populates="contacts")
    owner: Mapped["User"] = relationship(back_populates="contacts")
    leads: Mapped[List["Lead"]] = relationship(back_populates="contact")
    deals: Mapped[List["Deal"]] = relationship(back_populates="contact")
    tasks: Mapped[List["Task"]] = relationship(back_populates="contact")
    activities: Mapped[List["Activity"]] = relationship(back_populates="contact")
