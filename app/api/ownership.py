from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crud.user import get_user_by_id
from app.models.user import User

PRIVILEGED_CRM_ROLES = {"admin", "administrator", "sales_manager"}
READ_ALL_CRM_ROLES = PRIVILEGED_CRM_ROLES | {"viewer"}


def can_manage_all_crm_records(current_user: User) -> bool:
    return current_user.role.name in PRIVILEGED_CRM_ROLES


def can_read_crm_record(record_owner_id: int, current_user: User) -> bool:
    return current_user.role.name in READ_ALL_CRM_ROLES or record_owner_id == current_user.id


def ensure_can_read_crm_record(record_owner_id: int, current_user: User) -> None:
    if not can_read_crm_record(record_owner_id, current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions to access this record")


def ensure_can_modify_crm_record(record_owner_id: int, current_user: User) -> None:
    if can_manage_all_crm_records(current_user):
        return
    if record_owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions to modify this record")


def resolve_owner_id(db: Session, current_user: User, requested_owner_id: int | None) -> int:
    if requested_owner_id is None or requested_owner_id == current_user.id:
        return current_user.id
    if not can_manage_all_crm_records(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions to assign ownership")
    owner = get_user_by_id(db, user_id=requested_owner_id)
    if not owner:
        raise HTTPException(status_code=400, detail="Owner user does not exist")
    if not owner.is_active:
        raise HTTPException(status_code=400, detail="Owner user is inactive")
    return requested_owner_id
