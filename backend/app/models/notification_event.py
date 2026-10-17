from app.models.tenant import TenantOwned
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped,mapped_column
from app.db.session import Base
class NotificationEvent(TenantOwned, Base):
    __tablename__='notification_events'
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    task_id:Mapped[int]=mapped_column(ForeignKey('tasks.id',ondelete='CASCADE'),index=True)
