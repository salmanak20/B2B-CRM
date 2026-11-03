"""Pending organization access; invitations never grant membership by themselves."""
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.models.tenant import TenantOwned


class OrganizationInvitation(TenantOwned, Base):
    __tablename__ = "organization_invitations"
    __tenant_extra_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_org_invitation_email"),
        CheckConstraint("role IN ('owner','admin','sales_manager','sales_rep','viewer')", name="ck_invitation_role"),
        CheckConstraint("status IN ('pending','accepted','revoked')", name="ck_invitation_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    invited_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
