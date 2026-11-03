"""Server-only signup intents and durable, user-bound provisioning receipts."""
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class SignupIntent(Base):
    __tablename__ = "signup_intents"
    provider_user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class OrganizationProvision(Base):
    __tablename__ = "organization_provisions"
    __table_args__ = (UniqueConstraint("user_id", "request_key", name="uq_provision_user_request"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    request_key: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), unique=True, nullable=False)
