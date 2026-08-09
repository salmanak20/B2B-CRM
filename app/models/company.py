from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from datetime import datetime
from typing import List, Optional
from decimal import Decimal
from app.db.session import Base

class Company(Base):
    __tablename__ = "companies"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    industry: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    owner: Mapped["User"] = relationship(back_populates="companies")
    contacts: Mapped[List["Contact"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    leads: Mapped[List["Lead"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    deals: Mapped[List["Deal"]] = relationship(back_populates="company")
    tasks: Mapped[List["Task"]] = relationship(back_populates="company")
    activities: Mapped[List["Activity"]] = relationship(back_populates="company")
