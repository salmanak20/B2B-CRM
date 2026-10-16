"""Foundation constraints only: no tenant routing or authorization activation."""
from datetime import datetime, timezone
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from alembic import command
from alembic.config import Config

from app.db.session import Base
import app.models
from app.models.membership import Membership, MEMBERSHIP_ROLES
from app.models.tenant import CRM_REFERENCES, MEMBER_REFERENCES

TENANT_TABLES = {table.name for table in Base.metadata.tables.values() if "organization_id" in table.c and table.name != "memberships"}

@pytest.fixture
def tenant_engine():
    engine = sa.create_engine("sqlite:///:memory:")
    @sa.event.listens_for(engine, "connect")
    def enable_integrity(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with engine.begin() as db:
        roles = Base.metadata.tables["roles"]
        for index, name in enumerate(("admin", "sales_manager", "sales_rep", "viewer"), 1):
            db.execute(roles.insert().values(id=index, name=name))
        users = Base.metadata.tables["users"]
        for user_id in (1, 2):
            db.execute(users.insert().values(id=user_id, name="User", email=f"{user_id}@example.test", password_hash="fixture-only", role_id=1, is_active=True))
        for org in (1, 2):
            db.execute(Base.metadata.tables["organizations"].insert().values(id=org, name="Organization", slug=f"org-{org}"))
            db.execute(Membership.__table__.insert().values(organization_id=org, user_id=1, role="admin"))
        db.execute(Membership.__table__.insert().values(organization_id=2, user_id=2, role="viewer"))
        for org in (1, 2):
            for name in ("companies", "contacts", "leads", "pipelines", "pipeline_stages", "deals", "tasks", "activities", "workspace_settings", "workflow_rules", "workflow_runs", "notifications", "attachments", "audit_logs", "notification_events"):
                table = Base.metadata.tables[name]
                values = {"id": str(org) if name == "notification_events" else org, "organization_id": org}
                for column in table.c:
                    if column.name in values:
                        continue
                    if column.name in CRM_REFERENCES.get(name, {}):
                        values[column.name] = org
                    elif column.name in MEMBER_REFERENCES.get(name, ()):
                        values[column.name] = 1
                    elif not column.nullable and column.default is None and column.server_default is None:
                        if isinstance(column.type, sa.Boolean):
                            values[column.name] = False
                        elif isinstance(column.type, (sa.Integer, sa.Numeric)):
                            values[column.name] = 0
                        elif isinstance(column.type, sa.DateTime):
                            values[column.name] = datetime.now(timezone.utc)
                        else:
                            values[column.name] = f"fixture-{org}"
                if name == "activities": values["type"] = "note"
                if name == "leads": values["status"] = "new"
                if name == "workspace_settings": values["currency"] = "USD"
                db.execute(table.insert().values(**values))
    yield engine
    engine.dispose()


def test_all_tenant_models_have_nullable_indexed_keys():
    assert TENANT_TABLES == {"companies", "contacts", "leads", "deals", "pipelines", "pipeline_stages", "tasks", "activities", "workspace_settings", "workflow_rules", "workflow_runs", "notifications", "attachments", "audit_logs", "notification_events"}
    for name in TENANT_TABLES:
        table = Base.metadata.tables[name]
        assert table.c.organization_id.nullable
        assert any(list(index.columns.keys()) == ["organization_id"] for index in table.indexes)
        assert any(list(constraint.columns.keys()) == ["organization_id", "id"] for constraint in table.constraints if isinstance(constraint, sa.UniqueConstraint))


@pytest.mark.parametrize("table,column", [(table, column) for table, refs in CRM_REFERENCES.items() for column in refs])
def test_cross_tenant_crm_links_rejected_at_commit(tenant_engine, table, column):
    model = Base.metadata.tables[table]
    with pytest.raises(IntegrityError), tenant_engine.begin() as db:
        db.execute(model.update().where(model.c.organization_id == 1).values(**{column: 2}))


@pytest.mark.parametrize("table,column", [(table, column) for table, refs in MEMBER_REFERENCES.items() for column in refs])
def test_nonmember_user_links_rejected_at_commit(tenant_engine, table, column):
    model = Base.metadata.tables[table]
    with pytest.raises(IntegrityError), tenant_engine.begin() as db:
        db.execute(model.update().where(model.c.organization_id == 1).values(**{column: 2}))


@pytest.mark.parametrize("role", MEMBERSHIP_ROLES)
def test_membership_roles_reuse_permission_definitions(tenant_engine, role):
    with tenant_engine.begin() as db:
        db.execute(Membership.__table__.update().where(Membership.organization_id == 1).values(role=role, permission_role_name="admin" if role == "owner" else role))
        assert db.scalar(sa.select(Membership.permission_role_name).where(Membership.organization_id == 1)) == ("admin" if role == "owner" else role)


@pytest.mark.parametrize("values", [{"role": "superuser", "permission_role_name": "admin"}, {"role": "viewer", "permission_role_name": "admin"}])
def test_invalid_membership_roles_rejected(tenant_engine, values):
    with pytest.raises(IntegrityError), tenant_engine.begin() as db:
        db.execute(Membership.__table__.update().where(Membership.organization_id == 1).values(**values))


def test_membership_unique_per_organization_and_user(tenant_engine):
    with pytest.raises(IntegrityError), tenant_engine.begin() as db:
        db.execute(Membership.__table__.insert().values(organization_id=1, user_id=1, role="viewer"))


def test_pipeline_names_scoped_and_legacy_uniqueness_preserved(tenant_engine):
    table = Base.metadata.tables["pipelines"]
    with tenant_engine.begin() as db:
        db.execute(table.update().values(name="Same name"))  # Different organizations.
        db.execute(table.insert().values(name="Legacy", organization_id=None))
    for org, name in ((1, "Same name"), (None, "Legacy")):
        with pytest.raises(IntegrityError), tenant_engine.begin() as db:
            db.execute(table.insert().values(name=name, organization_id=org))


def test_settings_unique_per_organization(tenant_engine):
    with pytest.raises(IntegrityError), tenant_engine.begin() as db:
        db.execute(Base.metadata.tables["workspace_settings"].insert().values(organization_id=1))


def test_nullable_legacy_records_still_accepted(tenant_engine):
    with tenant_engine.begin() as db:
        result = db.execute(Base.metadata.tables["companies"].insert().values(name="Unmapped legacy", owner_id=2))
        assert db.scalar(sa.select(Base.metadata.tables["companies"].c.organization_id).where(Base.metadata.tables["companies"].c.id == result.inserted_primary_key[0])) is None


def test_assigned_child_cannot_reference_unmapped_parent(tenant_engine):
    with pytest.raises(IntegrityError), tenant_engine.begin() as db:
        db.execute(Base.metadata.tables["companies"].update().where(Base.metadata.tables["companies"].c.id == 1).values(organization_id=None))



def test_same_user_can_hold_different_organization_roles(tenant_engine):
    with tenant_engine.begin() as db:
        db.execute(Membership.__table__.update().where(Membership.organization_id == 2, Membership.user_id == 1).values(role="viewer", permission_role_name="viewer"))
        assert db.execute(sa.select(Membership.organization_id, Membership.role).where(Membership.user_id == 1).order_by(Membership.organization_id)).all() == [(1, "admin"), (2, "viewer")]
        assert db.scalar(sa.select(Base.metadata.tables["users"].c.role_id).where(Base.metadata.tables["users"].c.id == 1)) == 1


def test_existing_set_null_delete_behavior_preserved(tenant_engine):
    # WorkflowRun.task_id already uses SET NULL, event rows use CASCADE.
    with tenant_engine.begin() as db:
        db.execute(Base.metadata.tables["tasks"].delete().where(Base.metadata.tables["tasks"].c.id == 1))
        assert db.scalar(sa.select(Base.metadata.tables["workflow_runs"].c.task_id).where(Base.metadata.tables["workflow_runs"].c.id == 1)) is None
        assert db.scalar(sa.select(sa.func.count()).select_from(Base.metadata.tables["notification_events"]).where(Base.metadata.tables["notification_events"].c.organization_id == 1)) == 0


def test_postgresql_additive_migration_preserves_legacy_records():
    url = os.environ.get("CRM_TEST_MIGRATION_URL")
    if not url:
        pytest.skip("Requires isolated localhost CRM_TEST_MIGRATION_URL")
    target = urlparse(url)
    if os.environ.get("CRM_TEST_RUN") != "1" or target.hostname not in {"localhost", "127.0.0.1"} or not target.path.startswith("/crm_test"):
        pytest.fail("Refusing migration tests outside an explicitly isolated localhost crm_test database")
    assert os.environ.get("DATABASE_URL") == url
    engine = sa.create_engine(url)
    assert sa.inspect(engine).get_table_names() == [], "Migration test requires an empty disposable database"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "f8b3015a0001")
    with engine.begin() as db:
        db.execute(sa.text("INSERT INTO roles (id,name) VALUES (41,'admin')"))
        db.execute(sa.text("INSERT INTO users (id,name,email,password_hash,role_id,is_active) VALUES (51,'Legacy','legacy@example.test','fixture-only',41,true)"))
        db.execute(sa.text("INSERT INTO companies (id,name,owner_id) VALUES (61,'Existing company',51)"))
        db.execute(sa.text("INSERT INTO workspace_settings (id,name,timezone,currency) VALUES (1,'Existing workspace','UTC','USD')"))
        db.execute(sa.text("INSERT INTO pipelines (id,name,is_default,is_active) VALUES (71,'Existing pipeline',true,true)"))
    legacy_ids = {name: 100 + index for index, name in enumerate(("companies", "contacts", "leads", "pipelines", "pipeline_stages", "deals", "tasks", "activities", "workspace_settings", "workflow_rules", "workflow_runs", "notifications", "attachments", "audit_logs", "notification_events"))}
    legacy_ids.update(companies=61, pipelines=71, workspace_settings=1, notification_events="legacy-event")
    with engine.begin() as db:
        for name, record_id in legacy_ids.items():
            if name in {"companies", "pipelines", "workspace_settings"}:
                continue
            table = Base.metadata.tables[name]
            values = {"id": record_id}
            for column in table.c:
                if column.name in values or column.name == "organization_id":
                    continue
                if column.name in CRM_REFERENCES.get(name, {}):
                    values[column.name] = legacy_ids[CRM_REFERENCES[name][column.name]]
                elif column.name in MEMBER_REFERENCES.get(name, ()):
                    values[column.name] = 51
                elif not column.nullable and column.default is None and column.server_default is None:
                    if isinstance(column.type, sa.Boolean): values[column.name] = False
                    elif isinstance(column.type, (sa.Integer, sa.Numeric)): values[column.name] = 0
                    elif isinstance(column.type, sa.DateTime): values[column.name] = datetime.now(timezone.utc)
                    else: values[column.name] = "Legacy value"
            if name == "activities": values["type"] = "note"
            if name == "leads": values["status"] = "new"
            db.execute(table.insert().values(**values))
        original_columns = {name: [column["name"] for column in sa.inspect(db).get_columns(name)] for name in sa.inspect(db).get_table_names() if name != "alembic_version"}
        before = {name: db.execute(sa.text(f'SELECT * FROM "{name}"')).mappings().all() for name in original_columns}
    command.upgrade(config, "a1b2c3d4e501")
    with engine.connect() as db:
        for name, columns in original_columns.items():
            selected = ", ".join(f'"{column}"' for column in columns)
            assert db.execute(sa.text(f'SELECT {selected} FROM "{name}"')).mappings().all() == before[name]
        inspector = sa.inspect(db)
        for name in TENANT_TABLES:
            table = Base.metadata.tables[name]
            actual_fks = {fk["name"]: fk for fk in inspector.get_foreign_keys(name)}
            for fk in table.foreign_key_constraints:
                if fk.name:
                    assert actual_fks[fk.name]["constrained_columns"] == list(fk.column_keys)
                    assert actual_fks[fk.name]["referred_columns"] == [element.column.name for element in fk.elements]
            actual_indexes = {index["name"]: index for index in inspector.get_indexes(name)}
            for index in table.indexes:
                assert actual_indexes[index.name]["column_names"] == list(index.columns.keys())
                assert actual_indexes[index.name]["unique"] == bool(index.unique)
        assert db.scalar(sa.text("SELECT version_num FROM alembic_version")) == "a1b2c3d4e501"
        assert db.execute(sa.text("SELECT id,name,owner_id,organization_id FROM companies")).one() == (61, "Existing company", 51, None)
        assert db.scalar(sa.text("SELECT COUNT(*) FROM organizations")) == 0
        assert db.scalar(sa.text("SELECT COUNT(*) FROM memberships")) == 0
        assert db.execute(sa.text("SELECT id,name,organization_id FROM pipelines")).one() == (71,"Existing pipeline",None)
        assert db.execute(sa.text("SELECT id,name,organization_id FROM workspace_settings")).one() == (1,"Existing workspace",None)
        for name in TENANT_TABLES:
            assert next(column for column in sa.inspect(db).get_columns(name) if column["name"] == "organization_id")["nullable"]
        assert db.scalar(sa.text("SELECT COUNT(*) FROM pg_class WHERE relname IN ('organizations','memberships') AND relrowsecurity")) == 2
    command.downgrade(config, "f8b3015a0001")
    with engine.connect() as db:
        assert db.execute(sa.text("SELECT id,name,owner_id FROM companies")).one() == (61,"Existing company",51)
    command.upgrade(config, "a1b2c3d4e501")
    # Validate real PostgreSQL constraint enforcement, including deferred commit checks.
    with engine.begin() as db:
        db.execute(sa.text("INSERT INTO organizations (id,name,slug) VALUES (1,'One','one'),(2,'Two','two')"))
        db.execute(sa.text("INSERT INTO memberships (organization_id,user_id,role,permission_role_name) VALUES (1,51,'owner','admin'),(2,51,'admin','admin')"))
        # Assign the complete reviewed fixture graph atomically, just as a future
        # approved backfill must do; this never infers real customer ownership.
        for name in TENANT_TABLES:
            db.execute(sa.text(f'UPDATE "{name}" SET organization_id=1'))
    with pytest.raises(IntegrityError), engine.begin() as db:
        db.execute(sa.text("INSERT INTO contacts (id,company_id,owner_id,name,first_name,organization_id) VALUES (81,61,51,'Wrong tenant','Wrong',2)"))
    with pytest.raises(RuntimeError, match="Refusing tenant downgrade"):
        command.downgrade(config, "f8b3015a0001")
    with engine.connect() as db:
        assert db.scalar(sa.text("SELECT version_num FROM alembic_version")) == "a1b2c3d4e501"
        assert db.scalar(sa.text("SELECT COUNT(*) FROM organizations")) == 2
    engine.dispose()
