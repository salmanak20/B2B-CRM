"""Exercise pooled-host configuration with real disposable PostgreSQL clients."""
from pathlib import Path
import runpy
import psycopg
import pytest
import sqlalchemy as sa
from sqlalchemy.pool import NullPool
from app.core.config import settings
from tests.test_tenant_isolation import isolation_engine


@pytest.mark.parametrize('port',[5432,6543])
def test_managed_pooler_releases_every_client_and_disables_prepared_statements(isolation_engine,monkeypatch,port):
    actual_create=sa.create_engine
    real_url=isolation_engine.url.set(drivername='postgresql').render_as_string(hide_password=False)
    clients=[]
    def safe_create(url,**kwargs):
        assert sa.engine.make_url(url).host=='aws-0-test.pooler.supabase.com'
        assert kwargs['connect_args']['sslmode']=='require'
        assert kwargs['hide_parameters'] is True
        def connect():
            connection=psycopg.connect(real_url,prepare_threshold=kwargs['connect_args']['prepare_threshold'])
            clients.append(connection)
            return connection
        return actual_create(isolation_engine.url,creator=connect,**kwargs)
    monkeypatch.setattr(sa,'create_engine',safe_create)
    monkeypatch.setattr(settings,'DATABASE_URL',f'postgresql+psycopg://fixture:fixture@aws-0-test.pooler.supabase.com:{port}/postgres')
    loaded=runpy.run_path(str(Path(__file__).resolve().parents[1]/'app/db/session.py'))
    engine=loaded['engine']
    try:
        assert isinstance(engine.pool,NullPool)
        for _ in range(20):
            with engine.connect() as db:
                assert db.scalar(sa.text('SELECT 1'))==1
                assert clients[-1].prepare_threshold is None
            assert clients[-1].closed
        assert len(clients)==20 and all(connection.closed for connection in clients)
    finally:engine.dispose()
