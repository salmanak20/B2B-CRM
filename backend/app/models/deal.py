from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Deal(Base):
    __tablename__ = "deals"
    __table_args__ = (
        CheckConstraint("value >= 0", name="ck_deals_value_non_negative"),
        CheckConstraint("probability >= 0 AND probability <= 100", name="ck_deals_probability_range"),
        CheckConstraint("status IN ('open', 'won', 'lost')", name="ck_deals_status_values"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True, nullable=True)
    contact_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), index=True, nullable=True)
    lead_id: Mapped[Optional[int]] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"), index=True, nullable=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"), index=True, nullable=False)
    stage_id: Mapped[int] = mapped_column(ForeignKey("pipeline_stages.id"), index=True, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    probability: Mapped[int] = mapped_column(default=0, nullable=False)
    expected_close_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True, default="open", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    owner: Mapped["User"] = relationship(back_populates="deals")
    company: Mapped[Optional["Company"]] = relationship(back_populates="deals")
    contact: Mapped[Optional["Contact"]] = relationship(back_populates="deals")
    lead: Mapped[Optional["Lead"]] = relationship(back_populates="deals")
    pipeline: Mapped["Pipeline"] = relationship(back_populates="deals")
    stage: Mapped["PipelineStage"] = relationship(back_populates="deals")
    tasks: Mapped[list["Task"]] = relationship(back_populates="deal")
    activities: Mapped[list["Activity"]] = relationship(back_populates="deal")
