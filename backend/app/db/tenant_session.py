"""Fail-closed API/worker session. Offline migrations/backfills use separate connections."""
from fastapi import HTTPException
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session, with_loader_criteria
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import TextClause


def organization_id(db):
    value = db.info.get("organization_id")
    if not isinstance(value, int) or value <= 0:
        raise HTTPException(403, "Active organization membership is required")
    from app.models.organization import Organization
    suspended=db.connection().execute(select(Organization.__table__.c.is_suspended).where(Organization.__table__.c.id==value)).scalar_one_or_none()
    if suspended is not False:raise HTTPException(403,"Business workspace is suspended or unavailable")
    return value


def require_member(db, user_id):
    from app.models.membership import Membership
    from app.models.user import User
    member = db.scalar(select(Membership).join(User).where(
        Membership.organization_id == organization_id(db), Membership.user_id == user_id,
        Membership.is_active.is_(True), User.is_active.is_(True)))
    if not member:
        raise HTTPException(422, "User is not an active organization member")
    return member


class TenantSession(Session):
    def get(self, entity, ident, **kwargs):
        from app.models.tenant import TenantOwned
        from app.models.user import User
        if issubclass(entity, TenantOwned):
            org = organization_id(self)
            result = super().get(entity, ident, **kwargs)
            return result if result is None or result.organization_id == org else None
        if entity is User and self.info.get("organization_id"):
            # Avoid identity-map shortcuts for global users shared across organizations.
            return self.scalar(select(User).where(User.id == ident))
        return super().get(entity, ident, **kwargs)


@event.listens_for(TenantSession, "do_orm_execute")
def scope_queries(state):
    from app.models.tenant import TenantOwned
    from app.models.membership import Membership
    from app.models.user import User
    from app.db.session import Base
    tenant_tables={m.local_table.name for m in Base.registry.mappers if issubclass(m.class_,TenantOwned)}
    statement = state.statement
    if isinstance(statement, TextClause):
        raise HTTPException(403, "Raw SQL is unavailable in application sessions")
    touches_tenant = any(getattr(node, "name", None) in tenant_tables
                         for node in visitors.iterate(statement))
    org = state.session.info.get("organization_id")
    if touches_tenant and not org:
        organization_id(state.session)
    if touches_tenant and not state.is_orm_statement:
        raise HTTPException(403, "Tenant queries must use mapped models")
    if not org:
        return
    organization_id(state.session)
    from app.db.session import Base
    for mapped in Base.registry.mappers:
        model=mapped.class_
        if issubclass(model,TenantOwned):
            statement=statement.options(with_loader_criteria(model,model.organization_id==org,include_aliases=True))
    users = select(Membership.user_id).where(Membership.organization_id == org)
    statement = statement.options(with_loader_criteria(User, User.id.in_(users), include_aliases=True))
    mapper = state.bind_mapper
    if mapper and issubclass(mapper.class_, TenantOwned):
        if state.is_column_load or state.is_update or state.is_delete:
            statement = statement.where(mapper.class_.organization_id == org)
        if state.is_insert:
            raise HTTPException(403, "Use validated ORM objects for tenant inserts")
        if state.is_update:
            # Bulk changes bypass before_flush validation; only notification read flags
            # are used by the current application. Other updates must use ORM objects.
            values = getattr(statement, "_values", {}) or {}
            if mapper.class_.__tablename__ != "notifications" or any(getattr(k, "key", k) != "is_read" for k in values):
                raise HTTPException(403, "Bulk tenant updates are unavailable")
    state.statement = statement


@event.listens_for(TenantSession, "before_flush")
def validate_writes(db, flush_context, instances):
    from app.models.tenant import TenantOwned, CRM_REFERENCES, MEMBER_REFERENCES
    from app.db.session import Base
    from app.models.membership import Membership
    from app.models.user import User
    from app.models.workspace import Attachment
    from app.models.notification import Notification
    from app.models.audit_log import AuditLog
    models = {mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers}
    objects = list(db.new) + list(db.dirty) + list(db.deleted)
    for obj in objects:
        if isinstance(obj, Membership) and obj.organization_id != organization_id(db):
            raise HTTPException(403, "Cross-organization membership writes are forbidden")
        if isinstance(obj, User) and obj not in db.new and db.info.get("organization_id"):
            state = inspect(obj)
            if obj in db.deleted or state.attrs.role_id.history.has_changes() or state.attrs.is_active.history.has_changes():
                raise HTTPException(403, "Tenant administrators cannot change global account access")
    tenant_objects = [obj for obj in objects if isinstance(obj, TenantOwned)]
    if not tenant_objects:
        return
    org = organization_id(db)
    # Stamp all new objects before validating edges in an unflushed graph.
    for obj in tenant_objects:
        if obj in db.new and obj.organization_id is None:
            obj.organization_id = org
        history = inspect(obj).attrs.organization_id.history
        if obj.organization_id != org or any(old != org for old in history.deleted):
            raise HTTPException(403, "Cross-organization writes are forbidden")
    for obj in tenant_objects:
        if obj in db.deleted:
            continue
        for column, table in CRM_REFERENCES.get(obj.__tablename__, {}).items():
            value = getattr(obj, column)
            if value is not None and db.get(models[table], value) is None:
                raise HTTPException(422, "Related record is outside the active organization")
        for column in MEMBER_REFERENCES.get(obj.__tablename__, ()):
            value = getattr(obj, column)
            if value is not None and (obj in db.new or inspect(obj).attrs[column].history.has_changes()):
                if isinstance(obj,AuditLog) and value==db.info.get("actor_id"):
                    # The authenticated actor may have just removed their own
                    # access. Preserve the audit with its retained historical FK.
                    continue
                require_member(db, value)
        if isinstance(obj, (Attachment, Notification)):
            entity = obj.entity if isinstance(obj, Attachment) else obj.related_entity
            value = obj.entity_id if isinstance(obj, Attachment) else obj.related_entity_id
            if entity is None and value is None:
                continue
            aliases = {"company": "companies", "contact": "contacts", "lead": "leads", "deal": "deals", "task": "tasks"}
            table = aliases.get(entity, entity)
            if table not in {"companies", "contacts", "leads", "deals", "tasks"} or db.get(models[table], value) is None:
                raise HTTPException(422, "Related record is outside the active organization")
