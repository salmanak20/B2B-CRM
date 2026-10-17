"""Private billing metadata; tenant reads always require an explicit organization filter."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String,Numeric,Integer,Boolean,JSON,DateTime,ForeignKey,CheckConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.db.session import Base

class SubscriptionPlan(Base):
    __tablename__='subscription_plans'
    __table_args__=(CheckConstraint('price IS NULL OR price >= 0',name='ck_plan_price'),CheckConstraint('seat_limit IS NULL OR seat_limit > 0',name='ck_plan_seats'))
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(30),unique=True,nullable=False)
    name:Mapped[str]=mapped_column(String(100),nullable=False)
    currency:Mapped[str]=mapped_column(String(3),nullable=False)
    price:Mapped[Decimal|None]=mapped_column(Numeric(14,2),nullable=True)
    billing_interval:Mapped[str]=mapped_column(String(10),nullable=False)
    entitlements:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    seat_limit:Mapped[int|None]=mapped_column(Integer,nullable=True)
    published:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    external_price_id:Mapped[str|None]=mapped_column(String(255),nullable=True)

class Subscription(Base):
    __tablename__='subscriptions'
    __table_args__=(CheckConstraint("status IN ('active','trialing','paused','expired','canceled')",name='ck_subscription_status'),CheckConstraint('ends_at IS NULL OR ends_at > starts_at',name='ck_subscription_dates'))
    id:Mapped[int]=mapped_column(primary_key=True)
    organization_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),unique=True,nullable=False)
    plan_id:Mapped[int]=mapped_column(ForeignKey('subscription_plans.id'),nullable=False)
    status:Mapped[str]=mapped_column(String(20),nullable=False)
    starts_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    ends_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    enforcement_enabled:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    external_customer_id:Mapped[str|None]=mapped_column(String(255),nullable=True)
    external_subscription_id:Mapped[str|None]=mapped_column(String(255),nullable=True,unique=True)
    provider_status:Mapped[str|None]=mapped_column(String(30),nullable=True)
    provider_updated_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    provider_order_id:Mapped[str|None]=mapped_column(String(30),nullable=True,index=True)
    past_due_since:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
