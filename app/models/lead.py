from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from datetime import datetime
from decimal import Decimal
from typing import Optional
from app.db.session import Base

class Lead(Base):
    __tablename__ = "leads"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True, nullable=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    estimated_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    lead_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    owner: Mapped["User"] = relationship(back_populates="leads")
    company: Mapped["Company"] = relationship(back_populates="leads")
    contact: Mapped["Contact"] = relationship(back_populates="leads")
    deals: Mapped[list["Deal"]] = relationship(back_populates="lead")
    tasks: Mapped[list["Task"]] = relationship(back_populates="lead")
    activities: Mapped[list["Activity"]] = relationship(back_populates="lead")
