"""Phase 1B safety and preservation tests in the existing disposable PG cluster."""
import copy
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa

from app.db.session import Base
from app.db.tenant_backfill import (
    MappingError, TENANT_TABLES, _snapshot, _tables, backfill, prepare_manifest, staging_engine,
)
from app.models.tenant import CRM_REFERENCES, MEMBER_REFERENCES


@pytest.fixture(scope="module")
def pg_engine():
    url = os.environ.get("CRM_TEST_MIGRATION_URL")
    if not url:
        pytest.skip("Use scripts/tenant_foundation_qa.py --backfill for isolated PostgreSQL")
    engine = staging_engine(url)
    assert engine.url.database.startswith("crm_test_") and os.environ.get("CRM_TEST_RUN") == "1"
    with engine.connect() as db:
        assert sa.inspect(db).get_table_names() == []
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "a1b2c3d4e501")
    yield engine
    engine.dispose()


@pytest.fixture
def legacy(pg_engine):
    # Synthetic fixture rows only; the runner destroys this entire isolated cluster.
    assert pg_engine.url.database.startswith("crm_test_")
    with pg_engine.begin() as db:
        tables = _tables(db)
        names = ",".join('public."' + n + '"' for n in sorted(tables))
        db.execute(sa.text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
        db.execute(sa.text("INSERT INTO roles(id,name) VALUES(1,'sales_rep'),(2,'viewer')"))
        db.execute(sa.text("INSERT INTO users(id,name,email,password_hash,role_id,is_active) VALUES(1,'Legacy fixture','legacy@example.test','fixture-only',1,true)"))
        for name in TENANT_TABLES:
            table = Base.metadata.tables[name]
            values = {"id": "event-1" if name == "notification_events" else 1}
            for column in table.c:
                if column.name in values or column.name == "organization_id":
                    continue
                if column.name in CRM_REFERENCES.get(name, {}) or column.name in MEMBER_REFERENCES.get(name, ()):
                    values[column.name] = 1
                elif not column.nullable and column.default is None and column.server_default is None:
                    if isinstance(column.type, sa.Boolean): values[column.name] = False
                    elif isinstance(column.type, (sa.Integer, sa.Numeric)): values[column.name] = 0
                    else: values[column.name] = "fixture"
            if name == "activities": values["type"] = "note"
            if name == "leads": values["status"] = "new"
            if name == "workspace_settings": values["currency"] = "USD"
            if name == "attachments": values.update(entity="company",entity_id=1)
            if name == "audit_logs": values.update(entity="User",entity_id=1)
            if name == "notifications": values.update(related_entity="task",related_entity_id=1)
            db.execute(table.insert().values(**values))
    return pg_engine


def approved(engine):
    return prepare_manifest(engine, approved_by="Synthetic test approval", approved_at="2026-10-16", verified_user_ids={1})


def contents(engine):
    with engine.connect() as db:
        return _snapshot(db, _tables(db))


def test_preservation_roles_relationships_nullable_keys_and_idempotency(legacy):
    manifest = approved(legacy)
    before = contents(legacy)
    assert backfill(legacy, manifest)["errors"] == []
    assert contents(legacy) == before  # Dry run cannot write.
    result = backfill(legacy, manifest, apply=True)
    assert result["updated_rows"] == 15 and result["preservation_verified"] and result["nullable_tenant_columns"]
    after = contents(legacy)
    org_id = result["organization_id"]
    for name in before:
        if name in {"organizations", "memberships"}: continue
        expected = [dict(r, organization_id=org_id) for r in before[name]] if name in TENANT_TABLES else before[name]
        assert after[name] == expected
    assert len(after["organizations"]) == len(after["memberships"]) == 1
    assert after["memberships"][0]["role"] == after["memberships"][0]["permission_role_name"] == "sales_rep"
    assert after["users"][0]["auth_user_id"] is None
    assert backfill(legacy, manifest, apply=True)["updated_rows"] == 0
    assert contents(legacy) == after  # Including organization/membership timestamps.


@pytest.mark.parametrize("case", ["missing_id", "unknown_id", "duplicate_id", "owner", "role", "unverified", "approval", "duplicate_member"])
def test_invalid_mapping_rejected_without_writes(legacy, case):
    manifest = approved(legacy)
    if case == "missing_id": manifest["assignments"]["companies"] = []
    if case == "unknown_id": manifest["assignments"]["companies"] = [999]
    if case == "duplicate_id": manifest["assignments"]["companies"] = [1,1]
    if case == "owner": manifest["organization"]["owners"] = [1]
    if case == "role": manifest["memberships"][0]["role"] = "owner"
    if case == "unverified": manifest["memberships"][0]["verified"] = False
    if case == "approval": manifest["approved_by"] = ""
    if case == "duplicate_member": manifest["memberships"].append(copy.deepcopy(manifest["memberships"][0]))
    before = contents(legacy)
    assert backfill(legacy, manifest)["errors"]
    with pytest.raises(MappingError): backfill(legacy, manifest, apply=True)
    assert contents(legacy) == before


def test_changed_baseline_rejected(legacy):
    manifest = approved(legacy)
    with legacy.begin() as db:
        db.execute(sa.text("UPDATE companies SET name='Concurrent edit' WHERE id=1"))
    before = contents(legacy)
    with pytest.raises(MappingError, match="Baseline"): backfill(legacy, manifest, apply=True)
    assert contents(legacy) == before


@pytest.mark.parametrize("entity,entity_id", [("company",999), ("unknown",1), ("User",999)])
def test_orphaned_history_requires_review(legacy, entity, entity_id):
    with legacy.begin() as db:
        db.execute(sa.text("UPDATE audit_logs SET entity=:entity,entity_id=:record_id"),dict(entity=entity,record_id=entity_id))
    before = contents(legacy)
    with pytest.raises(MappingError, match="polymorphic"): backfill(legacy, approved(legacy), apply=True)
    assert contents(legacy) == before


def test_existing_tenant_conflict_rejected(legacy):
    with legacy.begin() as db:
        db.execute(sa.text("INSERT INTO organizations(id,name,slug) VALUES(8,'Other','other')"))
        db.execute(sa.text("UPDATE pipelines SET organization_id=8"))
    before = contents(legacy)
    with pytest.raises(MappingError, match="conflict"): backfill(legacy, approved(legacy), apply=True)
    assert contents(legacy) == before


def test_late_failure_rolls_back_all_writes(legacy):
    manifest, before = approved(legacy), contents(legacy)
    def fail_at_constraint_check(conn,cursor,statement,parameters,context,executemany):
        if statement == "SET CONSTRAINTS ALL IMMEDIATE":
            raise RuntimeError("Injected late failure")
    sa.event.listen(legacy, "before_cursor_execute", fail_at_constraint_check)
    try:
        with pytest.raises(RuntimeError,match="Injected late failure"):
            backfill(legacy, manifest, apply=True)
    finally:
        sa.event.remove(legacy,"before_cursor_execute",fail_at_constraint_check)
    assert contents(legacy) == before


@pytest.mark.parametrize("url", [
    "postgresql+psycopg://user:fixture@remote.example:5432/crm_tenant_staging",
    "postgresql+psycopg://user:fixture@127.0.0.1:5432/postgres",
    "postgresql+psycopg://user:fixture@127.0.0.1:5432/crm_tenant_staging?host=remote.example",
])
def test_nonstaging_urls_rejected_without_connection(url):
    with pytest.raises(MappingError): staging_engine(url)
