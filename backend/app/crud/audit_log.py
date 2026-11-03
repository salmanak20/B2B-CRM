from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogCreate
from typing import List

def get_audit_logs(db: Session, skip: int = 0, limit: int = 100) -> List[AuditLog]:
    return db.query(AuditLog).order_by(desc(AuditLog.timestamp)).offset(skip).limit(limit).all()

def create_audit_log(db: Session, obj_in: AuditLogCreate) -> AuditLog:
    db_obj = AuditLog(
        user_id=obj_in.user_id,
        action=obj_in.action,
        entity=obj_in.entity,
        entity_id=obj_in.entity_id,
        description=obj_in.description,
        ip_address=obj_in.ip_address
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def log_event(
    db: Session, 
    action: str, 
    user_id: int = None, 
    entity: str = None, 
    entity_id: int = None, 
    description: str = None, 
    ip_address: str = None
) -> AuditLog:
    # Authentication may succeed before a multi-membership user selects a tenant.
    # Do not write an unassigned CRM audit row or guess an organization.
    if not db.info.get("organization_id"):
        return None
    obj_in = AuditLogCreate(
        action=action,
        user_id=user_id,
        entity=entity,
        entity_id=entity_id,
        description=description,
        ip_address=ip_address
    )
    return create_audit_log(db, obj_in)
