"""Organization roles reuse global permission definitions, without changing User.role."""
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.session import Base

MEMBERSHIP_ROLES = ("owner", "admin", "sales_manager", "sales_rep", "viewer")

def permission_role_default(context):
    role = context.get_current_parameters()["role"]
    return "admin" if role == "owner" else role

class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_memberships_organization_user"),
        CheckConstraint("role IN ('owner','admin','sales_manager','sales_rep','viewer')", name="ck_memberships_role"),
        CheckConstraint("(role = 'owner' AND permission_role_name = 'admin') OR (role <> 'owner' AND permission_role_name = role)", name="ck_memberships_permission_role"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    permission_role_name: Mapped[str] = mapped_column(ForeignKey("roles.name"), nullable=False, default=permission_role_default)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    organization: Mapped["Organization"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship()
    permission_role: Mapped["Role"] = relationship()
