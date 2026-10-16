import hashlib
import asyncio
import logging
from datetime import datetime,timezone,timedelta
from sqlalchemy import select,delete
from sqlalchemy.exc import IntegrityError
from app.models.notification_event import NotificationEvent
from app.models.notification import Notification
from app.models.session import AuthSession,RateBucket
from app.models.task import Task

def deliver_due(db,user_id=None):
    from app.db.tenant_session import organization_id
    from app.models.membership import Membership
    from app.models.user import User
    org=organization_id(db)
    query=select(Task).where(Task.assigned_to_id.is_not(None),Task.status.in_(['pending','in_progress']),Task.due_date<=datetime.now(timezone.utc))
    query=query.where(Task.assigned_to_id.in_(select(Membership.user_id).join(User).where(
        Membership.organization_id==org,Membership.is_active.is_(True),User.is_active.is_(True))))
    if user_id is not None:query=query.where(Task.assigned_to_id==user_id)
    tasks=db.scalars(query).all();count=0
    for task in tasks:
        key=hashlib.sha256(f'{task.id}:{task.assigned_to_id}:{task.due_date.isoformat()}'.encode()).hexdigest()
        if db.get(NotificationEvent,key):continue
        try:
            with db.begin_nested():
                db.add(NotificationEvent(id=key,task_id=task.id));db.flush()
                db.add(Notification(user_id=task.assigned_to_id,title='Task due',message=task.title,notification_type='task_due',related_entity='task',related_entity_id=task.id))
                db.flush()
            count+=1
        except IntegrityError:
            # Another worker delivered the same task/deadline event.
            continue
    db.commit()
    return count

def tick():
    from app.db.session import SessionLocal
    from app.models.organization import Organization
    from app.core.config import settings
    if not settings.TENANT_ISOLATION_ENABLED:
        return
    with SessionLocal() as db:
        organizations=list(db.scalars(select(Organization.id)))
        db.execute(delete(AuthSession).where(AuthSession.expires_at<datetime.now(timezone.utc)))
        db.execute(delete(RateBucket).where(RateBucket.window_start<datetime.now(timezone.utc)-timedelta(days=2)))
        db.commit()
    for org in organizations:
        with SessionLocal() as db:
            db.info["organization_id"]=org
            deliver_due(db)

async def reminder_loop():
    while True:
        try:await asyncio.to_thread(tick)
        except Exception:logging.getLogger(__name__).warning('Reminder delivery failed; it will retry on the next interval.')
        await asyncio.sleep(60)
