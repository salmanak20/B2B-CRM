"""Private provider bindings and receipts. Never persist raw payloads or card data."""
from datetime import datetime
from sqlalchemy import String,ForeignKey,DateTime,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.db.session import Base

class BillingCheckout(Base):
    __tablename__='billing_checkouts'
    __table_args__=(UniqueConstraint('organization_id','request_key',name='uq_billing_checkout_request'),)
    token:Mapped[str]=mapped_column(String(64),primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),nullable=False,index=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    plan_id:Mapped[int]=mapped_column(ForeignKey('subscription_plans.id'),nullable=False)
    request_key:Mapped[str]=mapped_column(String(36),nullable=False)
    product_id:Mapped[str]=mapped_column(String(30),nullable=False)
    variant_id:Mapped[str]=mapped_column(String(30),nullable=False)
    provider_checkout_id:Mapped[str|None]=mapped_column(String(100),unique=True,nullable=True)
    checkout_url:Mapped[str|None]=mapped_column(String(2000),nullable=True)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    state:Mapped[str]=mapped_column(String(20),nullable=False)

class BillingEvent(Base):
    __tablename__='billing_events'
    digest:Mapped[str]=mapped_column(String(64),primary_key=True)
    event_name:Mapped[str]=mapped_column(String(80),nullable=False)
    resource_id:Mapped[str]=mapped_column(String(100),nullable=False)
    received_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
