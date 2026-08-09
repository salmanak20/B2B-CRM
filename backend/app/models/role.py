from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text
from typing import List
from app.db.session import Base

class Role(Base):
    __tablename__ = "roles"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    users: Mapped[List["User"]] = relationship(back_populates="role")
    permissions: Mapped[List["Permission"]] = relationship(
        secondary="role_permissions", back_populates="roles"
    )
