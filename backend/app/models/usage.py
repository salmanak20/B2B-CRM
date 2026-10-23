"""Private aggregate metadata: no customer record contents or identity payloads."""
from datetime import date, datetime
from sqlalchemy import ForeignKey, String, BigInteger, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class ResourceTotal(Base):
    __tablename__ = 'resource_totals'
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), primary_key=True)
    resource: Mapped[str] = mapped_column(String(30), primary_key=True)
    total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class ResourceDay(Base):
    __tablename__ = 'resource_days'
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    resource: Mapped[str] = mapped_column(String(30), primary_key=True)
    created: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    deleted: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    added_units: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    removed_units: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_activity: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class WorkflowPeriod(Base):
    __tablename__ = 'workflow_periods'
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), primary_key=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    executions: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class UsageInstrumentation(Base):
    __tablename__ = 'usage_instrumentation'
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
