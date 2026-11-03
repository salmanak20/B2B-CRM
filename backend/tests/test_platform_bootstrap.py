"""Bootstrap target guards run before any database or provider access."""
import pytest
from sqlalchemy.engine import make_url
from app.platform_bootstrap import validate_target, settings

REF = 'abcdefghijklmnopqrst'

@pytest.fixture(autouse=True)
def staging(monkeypatch):
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'staging')
    monkeypatch.setattr(settings, 'AUTH_PROVIDER', 'supabase')
    monkeypatch.setattr(settings, 'SUPABASE_URL', f'https://{REF}.supabase.co')

@pytest.mark.parametrize('host,user', [
    (f'db.{REF}.supabase.co', 'postgres'),
    ('aws-1-ap-northeast-1.pooler.supabase.com', f'postgres.{REF}'),
])
def test_explicit_matching_hosted_staging_requires_tls(host, user):
    url = make_url(f'postgresql+psycopg://{user}:fixture@{host}/postgres?sslmode=disable')
    target = validate_target(url, REF)
    assert target.query['sslmode'] == 'require'
    assert target.host == host and target.username == user

@pytest.mark.parametrize('change', ['production', 'development', 'legacy_auth', 'wrong_auth',
    'wrong_host', 'wrong_pool_user', 'wrong_database', 'wrong_driver', 'missing_ref',
    'invalid_ref', 'auth_query', 'auth_credentials', 'host_query', 'service_query',
    'wrong_port', 'direct_user'])
def test_hosted_target_mismatches_fail_closed(monkeypatch, change):
    url = make_url(f'postgresql+psycopg://postgres.{REF}:fixture@aws-1-ap-northeast-1.pooler.supabase.com/postgres')
    ref = REF
    if change in ('production', 'development'):
        monkeypatch.setattr(settings, 'ENVIRONMENT', change)
    elif change == 'legacy_auth': monkeypatch.setattr(settings, 'AUTH_PROVIDER', 'legacy')
    elif change == 'wrong_auth': monkeypatch.setattr(settings, 'SUPABASE_URL', 'https://different.supabase.co')
    elif change == 'wrong_host': url = url.set(host='production.invalid')
    elif change == 'wrong_pool_user': url = url.set(username='postgres.otherproject')
    elif change == 'wrong_database': url = url.set(database='production')
    elif change == 'wrong_driver': url = url.set(drivername='postgresql')
    elif change == 'missing_ref': ref = None
    elif change == 'invalid_ref': ref = 'invalid'
    elif change == 'auth_query': monkeypatch.setattr(settings, 'SUPABASE_URL', settings.SUPABASE_URL+'?project=other')
    elif change == 'auth_credentials': monkeypatch.setattr(settings, 'SUPABASE_URL', f'https://user@{REF}.supabase.co')
    elif change == 'host_query': url = url.update_query_dict({'host': 'production.invalid'})
    elif change == 'service_query': url = url.update_query_dict({'service': 'production'})
    elif change == 'wrong_port': url = url.set(port=6543)
    elif change == 'direct_user': url = url.set(host=f'db.{REF}.supabase.co', username='other')
    with pytest.raises(SystemExit): validate_target(url, ref)

def test_local_staging_retained_but_production_always_refused(monkeypatch):
    url = make_url('postgresql+psycopg://test:fixture@127.0.0.1/crm_test_bootstrap')
    assert validate_target(url) == url
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'production')
    with pytest.raises(SystemExit): validate_target(url)
