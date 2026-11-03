"""Explicit Phase 1B mapping rehearsal; no application routing or auth changes.

With TENANT_BACKFILL_STAGING_DATABASE_URL explicitly set, run from backend:
python -m app.db.tenant_backfill --manifest /private/approved-manifest.json
Append --apply only for the approved staging rehearsal. No production writes.
prepare_manifest requires separately verified user IDs; never infer an owner.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import sqlalchemy as sa

REVISION = "a1b2c3d4e501"
TENANT_TABLES = (
    "companies", "contacts", "leads", "pipelines", "pipeline_stages", "deals",
    "tasks", "activities", "workspace_settings", "workflow_rules", "workflow_runs",
    "notifications", "attachments", "audit_logs", "notification_events",
)
GLOBAL_TABLES = ("users", "roles", "permissions", "role_permissions", "auth_sessions", "rate_buckets")
ALIASES = dict(company="companies", contact="contacts", lead="leads", deal="deals",
               task="tasks", activity="activities", user="users", pipeline="pipelines",
               pipeline_stage="pipeline_stages", workflow_rule="workflow_rules",
               workflow_run="workflow_runs", attachment="attachments")


class MappingError(ValueError):
    pass


def staging_engine(url):
    """Never fall back to the application's DATABASE_URL or connect to a cloud host."""
    target = sa.engine.make_url(url)
    if (target.get_backend_name() != "postgresql" or target.host != "127.0.0.1"
            or not target.username or not target.port
            or not (target.database == "crm_tenant_staging" or (
                target.database.startswith("crm_test_") and os.environ.get("CRM_TEST_RUN") == "1"))
            or target.query):
        raise MappingError("Expected explicit isolated 127.0.0.1 staging/test PostgreSQL URL without query overrides")
    return sa.create_engine(target, echo=False, hide_parameters=True,
                            connect_args={"connect_timeout": 10, "application_name": "crm_phase1b_staging"})


def _identity(db):
    target = db.engine.url
    actual = db.execute(sa.text("SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port()")).one()
    if actual != (target.database, target.username, "127.0.0.1", target.port):
        raise MappingError("Staging server identity mismatch")
    if db.scalar(sa.text("SELECT version_num FROM public.alembic_version")) != REVISION:
        raise MappingError("Staging must be at Phase 1A revision")


def _tables(db):
    meta = sa.MetaData()
    for name in (*TENANT_TABLES, *GLOBAL_TABLES, "organizations", "memberships"):
        sa.Table(name, meta, autoload_with=db, schema="public")
    return {t.name: t for t in meta.tables.values()}


def _snapshot(db, tables):
    return {name: sorted([dict(r) for r in db.execute(sa.select(table)).mappings()],
                        key=lambda r: json.dumps(r, sort_keys=True, default=str))
            for name, table in tables.items()}


def _business(rows):
    return {name: [{k: v for k, v in row.items() if not (name in TENANT_TABLES and k == "organization_id")}
                   for row in values] for name, values in rows.items() if name not in {"organizations", "memberships"}}


def fingerprint(rows):
    return hashlib.sha256(json.dumps(_business(rows), sort_keys=True, default=str).encode()).hexdigest()


def _validate(rows, tables, manifest):
    errors = []
    org = manifest.get("organization", {})
    if org != {"name": "Legacy Organization", "slug": "legacy-organization", "owners": []}:
        errors.append("Only the approved Legacy Organization with no owner is supported")
    if manifest.get("version") != 1 or manifest.get("revision") != REVISION:
        errors.append("Unsupported manifest version or revision")
    if manifest.get("baseline_sha256") != fingerprint(rows):
        errors.append("Baseline fingerprint changed; review a new dry run")
    if not manifest.get("approved_by") or not manifest.get("approved_at"):
        errors.append("Mapping approval provenance is required")
    assignments = manifest.get("assignments", {})
    if set(assignments) != set(TENANT_TABLES):
        errors.append("Every tenant table must be explicitly mapped")
    for name in TENANT_TABLES:
        ids = assignments.get(name, [])
        if len(ids) != len(set(ids)) or set(ids) != {r["id"] for r in rows[name]}:
            errors.append(f"{name}: duplicate, unknown or unmapped record IDs")
    roles = {r["id"]: r["name"] for r in rows["roles"]}
    users = {r["id"]: r for r in rows["users"]}
    approved = manifest.get("memberships", [])
    members = {m["user_id"]: m for m in approved}
    if len(members) != len(approved) or set(members) != set(users):
        errors.append("Every legacy user needs one explicit verified membership")
    for user_id, member in members.items():
        user = users.get(user_id)
        if not user:
            errors.append(f"Unknown user {user_id}")
            continue
        role = roles.get(user["role_id"])
        if (role not in {"admin", "sales_manager", "sales_rep", "viewer"}
                or member.get("role") != role or member.get("is_active") is not user["is_active"]
                or member.get("verified") is not True):
            errors.append(f"User {user_id}: identity approval, role or active state mismatch")
    org_ids = {r["id"] for r in rows["organizations"] if r["slug"] == org.get("slug") and r["name"] == org.get("name")}
    if len(rows["organizations"]) != len(org_ids) or len(org_ids) > 1:
        errors.append("Existing organizations conflict with initial legacy mapping")
    for name in TENANT_TABLES:
        for row in rows[name]:
            if row["organization_id"] is not None and row["organization_id"] not in org_ids:
                errors.append(f"{name}/{row['id']}: conflicting tenant")
    for member in rows["memberships"]:
        expected = members.get(member["user_id"], {})
        if (member["organization_id"] not in org_ids or member["role"] != expected.get("role")
                or member["permission_role_name"] != expected.get("role")
                or member["is_active"] is not expected.get("is_active")):
            errors.append("Existing membership conflicts with manifest")
    # Check every declared FK, including ownership and member references.
    edges = 0
    for name, table in tables.items():
        for fk in table.foreign_key_constraints:
            target = next(iter(fk.elements)).column.table.name
            if target not in rows:
                errors.append(f"{name}: unsupported external FK")
                continue
            allowed = {tuple(r[e.column.name] for e in fk.elements) for r in rows[target]}
            for row in rows[name]:
                key = tuple(row[e.parent.name] for e in fk.elements)
                if any(v is None for v in key):
                    continue
                edges += 1
                if key not in allowed:
                    errors.append(f"{name}/{row.get('id')}: broken FK to {target}")
    for name in ("attachments", "audit_logs", "notifications"):
        entity_key, id_key = ("related_entity", "related_entity_id") if name == "notifications" else ("entity", "entity_id")
        for row in rows[name]:
            entity, record_id = row[entity_key], row[id_key]
            if entity is None and record_id is None:
                continue
            target = ALIASES.get(str(entity).lower(), str(entity).lower())
            if target not in {*TENANT_TABLES, "users"} or not any(r["id"] == record_id for r in rows.get(target, [])):
                errors.append(f"{name}/{row['id']}: ambiguous or orphaned polymorphic reference")
    stages = {r["id"]: r for r in rows["pipeline_stages"]}
    for deal in rows["deals"]:
        if deal["stage_id"] not in stages or stages[deal["stage_id"]]["pipeline_id"] != deal["pipeline_id"]:
            errors.append(f"deals/{deal['id']}: stage/pipeline mismatch")
    return errors, edges


def prepare_manifest(engine, *, approved_by, approved_at, verified_user_ids):
    """Prepare explicit mappings only after the caller has verified the users."""
    with engine.connect() as db, db.begin():
        db.execute(sa.text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        _identity(db)
        tables = _tables(db)
        rows = _snapshot(db, tables)
        roles = {r["id"]: r["name"] for r in rows["roles"]}
        return {"version": 1, "revision": REVISION, "baseline_sha256": fingerprint(rows),
                "organization": {"name": "Legacy Organization", "slug": "legacy-organization", "owners": []},
                "memberships": [{"user_id": u["id"], "role": roles.get(u["role_id"]),
                                 "is_active": u["is_active"], "verified": u["id"] in verified_user_ids} for u in rows["users"]],
                "assignments": {name: [r["id"] for r in rows[name]] for name in TENANT_TABLES},
                "approved_by": approved_by, "approved_at": approved_at}


def backfill(engine, manifest, *, apply=False):
    # Recheck the URL even for callers that supply an independently created engine.
    guard = staging_engine(engine.url)
    guard.dispose()
    with engine.connect() as db, db.begin():
        if apply:
            db.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
        else:
            db.execute(sa.text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        _identity(db)
        tables = _tables(db)
        if apply:
            quoted = ",".join('public."' + name + '"' for name in sorted(tables))
            db.execute(sa.text(f"LOCK TABLE {quoted} IN SHARE ROW EXCLUSIVE MODE"))
        before = _snapshot(db, tables)
        errors, edges = _validate(before, tables, manifest)
        report = {"mode": "apply" if apply else "dry_run", "errors": errors,
                  "counts": {name: len(r) for name, r in before.items()},
                  "proposed_assignments": manifest.get("assignments", {}),
                  "memberships": manifest.get("memberships", []), "foreign_key_edges_checked": edges,
                  "baseline_sha256": fingerprint(before), "updated_rows": 0}
        if errors:
            if apply:
                raise MappingError("; ".join(errors))
            return report
        if not apply:
            return report
        orgs, members = tables["organizations"], tables["memberships"]
        org_id = next((r["id"] for r in before["organizations"]), None)
        if org_id is None:
            org_id = db.execute(orgs.insert().values(name=manifest["organization"]["name"],
                slug=manifest["organization"]["slug"]).returning(orgs.c.id)).scalar_one()
        existing_members = {r["user_id"] for r in before["memberships"]}
        for member in manifest["memberships"]:
            if member["user_id"] not in existing_members:
                db.execute(members.insert().values(organization_id=org_id, user_id=member["user_id"],
                    role=member["role"], permission_role_name=member["role"], is_active=member["is_active"]))
        for name in TENANT_TABLES:
            table = tables[name]
            ids = manifest["assignments"][name]
            if ids:
                # Reflected Core tables have no ORM timestamp/onupdate callbacks.
                report["updated_rows"] += db.execute(table.update().where(
                    table.c.id.in_(ids), table.c.organization_id.is_(None)).values(organization_id=org_id)).rowcount
        db.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
        after = _snapshot(db, tables)
        errors, _ = _validate(after, tables, manifest)
        if errors or _business(before) != _business(after):
            raise MappingError("Post-write validation failed; transaction rolled back: " + "; ".join(errors))
        if any(r["organization_id"] != org_id for n in TENANT_TABLES for r in after[n]):
            raise MappingError("Unmapped records remain; transaction rolled back")
        report.update(organization_id=org_id, preservation_verified=True,
                      nullable_tenant_columns=all(tables[n].c.organization_id.nullable for n in TENANT_TABLES))
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    url = os.environ.get("TENANT_BACKFILL_STAGING_DATABASE_URL")
    if not url:
        parser.error("TENANT_BACKFILL_STAGING_DATABASE_URL must be explicitly configured")
    engine = staging_engine(url)
    try:
        print(json.dumps(backfill(engine, json.loads(args.manifest.read_text()), apply=args.apply), default=str))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
