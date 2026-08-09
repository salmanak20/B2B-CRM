from fastapi import APIRouter, Depends
from typing import List
from app.api.deps import SessionDep, CurrentActiveUser, require_permission
from app.schemas.audit_log import AuditLogResponse
from app.crud import audit_log as crud_audit_log

router = APIRouter()

@router.get("/", response_model=List[AuditLogResponse], dependencies=[Depends(require_permission("audit_logs.read"))])
def get_audit_logs(
    db: SessionDep,
    current_user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve audit logs.
    Only accessible by users with audit_logs.read permission (Admin, Sales Manager).
    """
    return crud_audit_log.get_audit_logs(db=db, skip=skip, limit=limit)
