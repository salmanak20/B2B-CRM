"""Nullable tenant metadata only; this module does not authorize requests."""
from sqlalchemy import ForeignKey, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

# CRM references enforce organization equality when both tenant keys are populated.
CRM_REFERENCES = {
    "contacts": {"company_id": "companies"},
    "leads": {"company_id": "companies", "contact_id": "contacts"},
    "deals": {"company_id": "companies", "contact_id": "contacts", "lead_id": "leads", "pipeline_id": "pipelines", "stage_id": "pipeline_stages"},
    "pipeline_stages": {"pipeline_id": "pipelines"},
    "tasks": {"company_id": "companies", "contact_id": "contacts", "lead_id": "leads", "deal_id": "deals"},
    "activities": {"company_id": "companies", "contact_id": "contacts", "lead_id": "leads", "deal_id": "deals"},
    "workflow_runs": {"rule_id": "workflow_rules", "lead_id": "leads", "task_id": "tasks"},
    "notification_events": {"task_id": "tasks"},
}
MEMBER_REFERENCES = {
    "organization_invitations": ("invited_by",),
    "companies": ("owner_id",), "contacts": ("owner_id",), "leads": ("owner_id",),
    "deals": ("owner_id",), "tasks": ("owner_id", "assigned_to_id"),
    "activities": ("user_id",), "notifications": ("user_id",),
    "audit_logs": ("user_id",), "workflow_rules": ("owner_id", "assigned_to_id"),
    "attachments": ("uploaded_by",),
}

class TenantOwned:
    @declared_attr
    def organization_id(cls) -> Mapped[int | None]:
        return mapped_column(ForeignKey("organizations.id", name=f"fk_{cls.__tablename__}_organization"),
                             nullable=True, index=True)

    @declared_attr.directive
    def __table_args__(cls):
        table = cls.__tablename__
        args = list(getattr(cls, "__tenant_extra_args__", ()))
        args.append(UniqueConstraint("organization_id", "id", name=f"uq_{table}_organization_id"))
        for column, target in CRM_REFERENCES.get(table, {}).items():
            args.extend((
                ForeignKeyConstraint(["organization_id", column], [f"{target}.organization_id", f"{target}.id"],
                                     name=f"fk_{table}_org_{column}", deferrable=True, initially="DEFERRED"),
                Index(f"ix_{table}_org_{column}", "organization_id", column),
            ))
        for column in MEMBER_REFERENCES.get(table, ()):
            args.extend((
                ForeignKeyConstraint(["organization_id", column], ["memberships.organization_id", "memberships.user_id"],
                                     name=f"fk_{table}_member_{column}", deferrable=True, initially="DEFERRED"),
                Index(f"ix_{table}_org_{column}", "organization_id", column),
            ))
        if table == "workspace_settings":
            args.append(UniqueConstraint("organization_id", name="uq_workspace_settings_organization"))
        if table == "pipelines":
            from sqlalchemy import text
            args.extend((
                UniqueConstraint("organization_id", "name", name="uq_pipelines_organization_name"),
                Index("uq_pipelines_legacy_name", "name", unique=True,
                      postgresql_where=text("organization_id IS NULL"), sqlite_where=text("organization_id IS NULL")),
            ))
        return tuple(args)
