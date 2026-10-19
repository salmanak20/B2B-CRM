"""Approved Pilot policy on disposable PostgreSQL; Auth and delivery are mocked."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from fastapi import HTTPException
from tests.test_subscriptions import foundation, control, business, api, isolation_engine, assign
from app.models import Membership, Company
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.invitation import OrganizationInvitation
from app.models.platform import PlatformAudit
from app.db.tenant_session import TenantSession
from app.core.sessions import utcnow, aware
from app.services.subscriptions import pilot_definition, PILOT_EXPIRED


@pytest.fixture
def pilot(foundation, control):
    client, engine, login, _, _ = foundation
    body = {**pilot_definition(), 'reason': 'Approved synthetic Pilot configuration'}
    result = client.put('/api/v1/platform/plans/free_pilot', json=body)
    assert result.status_code == 200, result.text
    pid = result.json()['id']
    with Session(engine) as db:
        db.scalar(sa.select(Membership).where(Membership.organization_id == 1, Membership.user_id == 1)).role = 'owner'
        db.commit()
    return client, engine, login, pid, control[3]


def approve(client, pid, **changes):
    return client.put('/api/v1/platform/subscriptions/1', json={
        'plan_id': pid, 'status': 'active', 'enforcement_enabled': True,
        'pilot_action': 'activate', 'approved_owner_id': 1, 'reason': 'Explicit synthetic owner approval', **changes})


def expire(engine):
    with Session(engine) as db:
        sub = db.scalar(sa.select(Subscription).where(Subscription.organization_id == 1))
        sub.starts_at = utcnow() - timedelta(days=31)
        sub.ends_at = utcnow() - timedelta(days=1)
        db.commit()
        return aware(sub.ends_at).isoformat()


def test_plan_and_activation_are_idempotent_with_server_controlled_dates(pilot):
    client, engine, login, pid, _ = pilot
    again = client.put('/api/v1/platform/plans/free_pilot', json={**pilot_definition(), 'reason': 'Retry'})
    assert again.status_code == 200 and again.json()['id'] == pid
    before = utcnow()
    result = approve(client, pid)
    assert result.status_code == 200, result.text
    data = result.json()
    sub = data['subscription']
    from datetime import datetime
    start = datetime.fromisoformat(sub['starts_at'])
    end = datetime.fromisoformat(sub['ends_at'])
    assert before <= start <= utcnow() and end - start == timedelta(days=30)
    assert data['seats'] == {'active': 1, 'pending': 0, 'limit': 5}
    assert all(data['entitlements'].values()) and float(data['plan']['price']) == 0
    assert not data['test_billing_available']
    assert approve(client, pid).json()['subscription'] == sub
    with Session(engine) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(SubscriptionPlan).where(SubscriptionPlan.code == 'free_pilot')) == 1
        assert db.scalar(sa.select(sa.func.count()).select_from(PlatformAudit).where(PlatformAudit.action == 'pilot_activate')) == 1
    login(1)
    assert client.get('/api/v1/companies', headers={'X-Organization-ID': '1'}).status_code == 200
    assert client.get('/api/v1/companies/2', headers={'X-Organization-ID': '1'}).status_code == 404
    assert approve(client, pid).status_code == 403


@pytest.mark.parametrize('change', [
    {'enforcement_enabled': False}, {'approved_owner_id': 2}, {'pilot_action': None},
    {'ends_at': '2099-01-01T00:00:00Z'}, {'external_subscription_id': 'invented'}])
def test_approval_requires_exact_policy_and_matching_owner(pilot, change):
    client, engine, _, pid, _ = pilot
    assert approve(client, pid, **change).status_code == 422
    with Session(engine) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(Subscription)) == 0
        assert db.scalar(sa.select(sa.func.count()).select_from(Membership).where(Membership.role == 'owner')) == 1


def test_unverified_owner_and_existing_subscription_cannot_be_adopted(pilot):
    client, engine, _, pid, ids = pilot
    ids[1]['email_confirmed_at'] = None
    assert approve(client, pid).status_code == 422
    ids[1]['email_confirmed_at'] = '2026-10-19T00:00:00Z'
    with Session(engine) as db:
        starter = db.scalar(sa.select(SubscriptionPlan.id).where(SubscriptionPlan.code == 'starter'))
    assert assign(client, starter).status_code == 200
    assert approve(client, pid).status_code == 409
    with Session(engine) as db:
        assert db.scalar(sa.select(Subscription.plan_id)) == starter


@pytest.mark.parametrize('change', [{'seat_limit': None}, {'price': 1}, {'entitlements': {'exports': True}}])
def test_fixed_pilot_configuration_cannot_be_weakened(pilot, change):
    client, engine, _, pid, _ = pilot
    assert client.put('/api/v1/platform/plans/free_pilot', json={**pilot_definition(), 'reason': 'Invalid policy', **change}).status_code == 422
    with Session(engine) as db:
        assert db.get(SubscriptionPlan, pid).seat_limit == 5


def test_expiry_blocks_stale_sessions_direct_apis_workers_and_preserves_data(pilot):
    client, engine, login, pid, _ = pilot
    assert approve(client, pid).status_code == 200
    login(1)
    h = {'X-Organization-ID': '1'}
    assert client.post('/api/v1/auth/organization', json={'organization_id': 1}).status_code == 200
    with Session(engine) as db:
        before = [tuple(r) for r in db.execute(sa.select(Company.__table__))]
        members = [tuple(r) for r in db.execute(sa.select(Membership.__table__))]
    expire(engine)
    for method, path, body in [
        ('GET', 'auth/me', None), ('GET', 'companies', None), ('POST', 'companies', {'name': 'Denied'}),
        ('PUT', 'companies/1', {'name': 'Denied'}), ('DELETE', 'companies/1', None),
        ('POST', 'team/invitations', {'email': 'no-email@example.com', 'name': 'Denied'}),
        ('GET', 'attachments/1/content', None), ('POST', 'records/companies/1/attachments', None),
        ('GET', 'exports/companies', None), ('GET', 'dashboard/summary', None)]:
        response = client.request(method, '/api/v1/' + path, headers=h, json=body)
        assert response.status_code == 403, (path, response.text)
        assert response.json()['detail'] == PILOT_EXPIRED
    assert client.post('/api/v1/auth/organization', json={'organization_id': 1}).status_code == 403
    from app.services.reminders import deliver_due
    from app.api.routes.workspace import run_lead_workflows
    for operation in [lambda db: db.scalars(sa.select(Company)).all(), deliver_due,
                      lambda db: run_lead_workflows(db, SimpleNamespace()),
                      lambda db: (db.add(Company(name='Denied', owner_id=1)), db.flush())]:
        with TenantSession(engine) as db:
            db.info.update(organization_id=1, actor_id=1)
            with pytest.raises(HTTPException, match='Free Pilot'):
                operation(db)
            db.rollback()
    with Session(engine) as db:
        assert [tuple(r) for r in db.execute(sa.select(Company.__table__))] == before
        assert [tuple(r) for r in db.execute(sa.select(Membership.__table__))] == members


def test_only_explicit_platform_renewal_restores_access_without_retry_extension(pilot):
    client, engine, login, pid, _ = pilot
    assert approve(client, pid).status_code == 200
    old_end = expire(engine)
    login(1)
    assert approve(client, pid, pilot_action='extend', expected_ends_at=old_end).status_code == 403
    login(3)
    assert approve(client, pid).status_code == 409
    result = approve(client, pid, pilot_action='extend', expected_ends_at=old_end)
    assert result.status_code == 200, result.text
    assert approve(client, pid, pilot_action='extend', expected_ends_at=old_end).status_code == 409
    login(1)
    assert client.get('/api/v1/companies', headers={'X-Organization-ID': '1'}).status_code == 200


def test_concurrent_admission_respects_five_seats_including_owner(pilot):
    client, engine, login, pid, _ = pilot
    assert approve(client, pid).status_code == 200
    with Session(engine) as db:
        for i in range(3):
            db.add(OrganizationInvitation(organization_id=1, email=f'pending{i}@example.com', name='Reserved',
                role='sales_rep', status='pending', invited_by=1, provider_user_id=str(i), expires_at=utcnow()+timedelta(days=1)))
        db.commit()
    from app.services.team import change_member
    def activate(uid):
        with TenantSession(engine, autoflush=False) as db:
            db.info.update(organization_id=1, actor_id=1)
            try:
                change_member(db, SimpleNamespace(id=1), uid, is_active=True, role='viewer')
                db.commit(); return 200
            except HTTPException as error:
                db.rollback(); return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(activate, [4, 5])) == [200, 409]
    login(1)
    result = client.get('/api/v1/subscription', headers={'X-Organization-ID': '1'}).json()
    assert result['seats'] == {'active': 2, 'pending': 3, 'limit': 5}


def test_platform_login_remains_available_when_its_workspace_expires(pilot):
    client, engine, login, pid, _ = pilot
    assert approve(client, pid).status_code == 200
    with Session(engine) as db:
        db.add(Membership(organization_id=1, user_id=3, role='viewer')); db.commit()
    old_end = expire(engine)
    login(3)
    assert client.get('/api/v1/platform/summary').status_code == 200
    assert approve(client, pid, pilot_action='extend', expected_ends_at=old_end).status_code == 200


def test_reminder_loop_skips_expired_pilot_and_continues_other_organizations(pilot, monkeypatch):
    client, engine, _, pid, _ = pilot
    assert approve(client, pid).status_code == 200
    expire(engine)
    from app.services import reminders
    from app.db import session
    monkeypatch.setattr(session, 'SessionLocal', lambda: TenantSession(engine))
    original = reminders.deliver_due
    processed = []
    def deliver(db):
        if db.info['organization_id'] == 1:
            return original(db)
        processed.append(db.info['organization_id'])
    monkeypatch.setattr(reminders, 'deliver_due', deliver)
    reminders.tick()
    assert processed == [2]


def test_expired_pilot_rejects_pending_invitation_acceptance_and_reactivation_bypass(pilot):
    client, engine, login, pid, _ = pilot
    assert approve(client, pid).status_code == 200
    login(1)
    invitation = client.post('/api/v1/team/invitations', headers={'X-Organization-ID': '1'},
        json={'name': 'Synthetic recipient', 'email': 'user2@example.com', 'role': 'sales_rep'})
    assert invitation.status_code == 200, invitation.text
    expire(engine)
    login(2)
    assert client.post(f"/api/v1/auth/invitations/{invitation.json()['id']}/accept").status_code == 403
    login(3)
    assert client.put('/api/v1/platform/organizations/1', json={'is_suspended': False, 'reason': 'Generic reactivation cannot renew Pilot'}).status_code == 200
    login(1)
    assert client.get('/api/v1/companies', headers={'X-Organization-ID': '1'}).status_code == 403
    with Session(engine) as db:
        assert db.scalar(sa.select(Membership).where(Membership.organization_id == 1, Membership.user_id == 2)) is None
