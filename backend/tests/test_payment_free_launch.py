"""Manual subscription administration with billing off; synthetic organizations only."""
import json
from uuid import uuid4
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from tests.test_subscriptions import foundation, control, business, api, isolation_engine, assign
from app.core.config import settings
from app.models import Membership, Company
from app.models.subscription import Subscription
from app.models.billing import BillingCheckout, BillingEvent
from app.models.platform import PlatformAudit


def test_manual_access_uses_existing_platform_controls_and_enforced_plan(foundation, monkeypatch):
    client, engine, login, pid, _ = foundation
    monkeypatch.setattr(settings, 'LEMON_SQUEEZY_TEST_ENABLED', False)
    with Session(engine) as db:
        member = db.scalar(sa.select(Membership).where(Membership.organization_id == 1, Membership.user_id == 1))
        member.role = 'owner'
        before = [tuple(row) for row in db.execute(sa.select(Company.__table__))]
        db.commit()
    change = {'is_suspended': True, 'reason': 'Synthetic manual review'}
    assert client.put('/api/v1/platform/organizations/1', json=change).status_code == 200
    login(1)
    assert assign(client, pid).status_code == 403
    assert client.put('/api/v1/platform/organizations/1', json={**change, 'is_suspended': False}).status_code == 403
    h = {'X-Organization-ID': '1'}
    assert client.get('/api/v1/companies', headers=h).status_code == 403
    login(3)
    assert assign(client, pid).status_code == 200
    assert client.put('/api/v1/platform/organizations/1', json={**change, 'is_suspended': False}).status_code == 200
    login(1)
    response = client.get('/api/v1/subscription', headers=h)
    assert response.status_code == 200
    data = response.json()
    assert data['seats']['limit'] == 2 and data['subscription']['enforcement_enabled']
    assert data['entitlements'] == {'analytics': True, 'exports': False, 'workflows': False, 'attachments': False}
    assert not data['test_billing_available'] and not data['billing_available']
    assert client.get('/api/v1/exports/companies', headers=h).status_code == 403
    assert client.get('/api/v1/companies/2', headers=h).status_code == 404
    assert client.get('/api/v1/dashboard/summary', headers=h).status_code == 200
    assert client.put('/api/v1/team/members/4', headers=h, json={'is_active': True, 'role': 'viewer'}).status_code == 200
    assert client.put('/api/v1/team/members/5', headers=h, json={'is_active': True, 'role': 'viewer'}).status_code == 409
    login(4)
    assert client.get('/api/v1/companies', headers=h).status_code == 200
    assert client.post('/api/v1/companies', headers=h, json={'name': 'Forbidden write'}).status_code == 403
    assert client.get('/api/v1/companies', headers={'X-Organization-ID': '2'}).status_code == 403
    with Session(engine) as db:
        assert [tuple(row) for row in db.execute(sa.select(Company.__table__))] == before
        assert set(db.scalars(sa.select(PlatformAudit.action))) >= {'subscription_configured', 'business_suspended', 'business_reactivated'}


@pytest.mark.parametrize('configured', [False, True])
def test_disabled_payments_do_not_call_provider_or_change_manual_access(foundation, monkeypatch, configured):
    client, engine, login, pid, _ = foundation
    assert assign(client, pid).status_code == 200
    for name in ('LEMON_SQUEEZY_TEST_API_KEY', 'LEMON_SQUEEZY_TEST_STORE_ID', 'LEMON_SQUEEZY_TEST_WEBHOOK_SECRET'):
        monkeypatch.setattr(settings, name, 'fixture-only' if configured else '')
    monkeypatch.setattr(settings, 'LEMON_SQUEEZY_TEST_ENABLED', False)
    def no_provider(*args, **kwargs):
        raise AssertionError('Disabled payments must never call the provider')
    monkeypatch.setattr('httpx.request', no_provider)
    login(1)
    h = {'X-Organization-ID': '1'}
    before = client.get('/api/v1/subscription', headers=h).json()
    assert client.post('/api/v1/billing/checkout', headers=h, json={'plan_id': pid, 'request_key': str(uuid4())}).status_code == 503
    assert client.post('/api/v1/billing/portal', headers=h).status_code == 503
    assert client.get('/api/v1/billing/history', headers=h).status_code == 503
    raw = json.dumps({'meta': {'event_name': 'subscription_created'}, 'data': {'id': '123'}}).encode()
    assert client.post('/api/v1/billing/webhook', content=raw).status_code == 503
    assert client.get('/api/v1/subscription?success=true&plan_id=999', headers=h).json() == before
    assert not before['entitlements']['exports']
    with Session(engine) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(Subscription)) == 1
        assert db.scalar(sa.select(sa.func.count()).select_from(BillingEvent)) == 0
        assert db.scalar(sa.select(sa.func.count()).select_from(BillingCheckout)) == 0
