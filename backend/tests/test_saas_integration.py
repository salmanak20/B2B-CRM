"""Cross-phase checks on disposable PostgreSQL; provider calls remain mocked."""
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from tests.test_lemon_billing import billing, foundation, control, business, api, isolation_engine
from app.models import Company
from app.models.tenant import TenantOwned


def test_billing_suspension_and_workspace_switch_preserve_private_crm(billing):
    client, engine, login, _, _, _, checkout, deliver, _ = billing
    assert client.post('/api/v1/auth/organization', json={'organization_id': 1}).status_code == 200
    created = client.post('/api/v1/companies', json={'name': 'Integration private company'})
    assert created.status_code == 200, created.text
    identifier = created.json()['id']
    with Session(engine) as db:
        before = dict(db.execute(sa.select(Company.__table__).where(Company.id == identifier)).mappings().one())
    assert checkout().status_code == 200
    assert deliver().status_code == 200
    assert deliver().status_code == 200
    assert client.get('/api/v1/subscription').json()['subscription']['status'] == 'active'
    assert client.post('/api/v1/auth/organization', json={'organization_id': 2}).status_code == 200
    assert client.get(f'/api/v1/companies/{identifier}').status_code == 404
    assert client.post('/api/v1/companies', json={'name': 'Viewer cannot write'}).status_code == 403
    login(3)
    assert client.get(f'/api/v1/companies/{identifier}', headers={'X-Organization-ID': '1'}).status_code == 403
    for suspended in (True, False):
        assert client.put('/api/v1/platform/organizations/1', json={'is_suspended': suspended, 'reason': 'Integration verification'}).status_code == 200
        login(1)
        assert client.get(f'/api/v1/companies/{identifier}', headers={'X-Organization-ID': '1'}).status_code == (403 if suspended else 200)
        login(3)
    with Session(engine) as db:
        assert dict(db.execute(sa.select(Company.__table__).where(Company.id == identifier)).mappings().one()) == before


def migration_config():
    return Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))


@pytest.fixture
def empty_schema(isolation_engine):
    # The imported fixture refuses any non-local/non-disposable database.
    with isolation_engine.begin() as db:
        names = ','.join('"' + n + '"' for n in sa.inspect(db).get_table_names() if n != 'alembic_version')
        db.execute(sa.text(f'TRUNCATE {names} RESTART IDENTITY CASCADE'))
    return isolation_engine


def test_complete_upgrade_and_empty_saas_rollback_preserve_legacy_rows(empty_schema):
    engine = empty_schema
    config = migration_config()
    command.downgrade(config, 'f8b3015a0001')
    with engine.begin() as db:
        db.execute(sa.text("INSERT INTO roles (id,name) VALUES (41,'admin')"))
        db.execute(sa.text("INSERT INTO users (id,name,email,password_hash,role_id,is_active) VALUES (51,'Legacy','legacy@example.test','fixture-only',41,true)"))
        db.execute(sa.text("INSERT INTO companies (id,name,owner_id) VALUES (61,'Existing company',51)"))
        columns = {name: [c['name'] for c in sa.inspect(db).get_columns(name)] for name in sa.inspect(db).get_table_names() if name != 'alembic_version'}
        def snapshot(connection):
            return {name: list(connection.execute(sa.text('SELECT ' + ','.join('"' + c + '"' for c in names) + ' FROM "' + name + '"')).mappings()) for name, names in columns.items()}
        before = snapshot(db)
    for _ in range(2):
        command.upgrade(config, 'head')
        with engine.connect() as db:
            assert snapshot(db) == before
            assert db.scalar(sa.text('SELECT version_num FROM alembic_version')) == 'a1b2c3d4e509'
            for name in ('organizations', 'memberships', 'subscription_plans', 'subscriptions', 'billing_checkouts', 'billing_events'):
                assert db.scalar(sa.text(f'SELECT count(*) FROM {name}')) == 0
            for model in TenantOwned.__subclasses__():
                assert next(c for c in sa.inspect(db).get_columns(model.__tablename__) if c['name'] == 'organization_id')['nullable']
        command.downgrade(config, 'f8b3015a0001')
        with engine.connect() as db:
            assert snapshot(db) == before
    command.upgrade(config, 'head')


def test_populated_billing_rollback_fails_atomically_and_recovers(empty_schema):
    engine = empty_schema
    with engine.begin() as db:
        db.execute(sa.text("INSERT INTO billing_events (digest,event_name,resource_id,received_at) VALUES (:digest,'subscription_created','fixture',now())"), {'digest': 'a' * 64})
    with pytest.raises(RuntimeError, match='Refusing to discard billing state'):
        command.downgrade(migration_config(), 'a1b2c3d4e506')
    command.upgrade(migration_config(), 'head')
    with engine.connect() as db:
        assert db.scalar(sa.text('SELECT version_num FROM alembic_version')) == 'a1b2c3d4e509'
        assert db.scalar(sa.text('SELECT count(*) FROM billing_events')) == 1
