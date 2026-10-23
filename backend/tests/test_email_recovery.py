"""Default Supabase email recovery: real sessions, mocked provider contracts."""
import base64
import hashlib
import json
import time
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import settings
from app.core.email_recovery import cookie_name
from app.core.sessions import cipher, session_key
from app.models.session import AuthSession
from tests.utils import create_user


@pytest.fixture
def recovery(client, db, monkeypatch):
    monkeypatch.setattr(settings,'AUTH_EMAIL_CONFIGURATION_VERIFIED',True)
    from app.api.routes import auth
    from app.core import sessions
    monkeypatch.setattr(settings, 'AUTH_PROVIDER', 'supabase')
    monkeypatch.setattr(settings, 'TENANT_ISOLATION_ENABLED', True)
    user = create_user(db)
    user.auth_user_id = str(uuid4())
    db.commit()
    identity = {'id': user.auth_user_id, 'email': user.email, 'email_confirmed_at': '2026-10-17T00:00:00Z'}
    calls, used = [], set()
    def provider(method, path, data=None, **kwargs):
        calls.append((method, path, data))
        if path.startswith('/recover?'):
            return {}
        if path == '/token?grant_type=pkce':
            assert set(data) == {'auth_code', 'code_verifier'}
            challenge = base64.urlsafe_b64encode(hashlib.sha256(data['code_verifier'].encode()).digest()).rstrip(b'=').decode()
            assert challenge == next(d['code_challenge'] for _, p, d in reversed(calls) if p.startswith('/recover?'))
            if data['auth_code'] != 'valid-one-use-code' or data['auth_code'] in used:
                raise HTTPException(401, 'Invalid or already used code')
            used.add(data['auth_code'])
            return {'user': dict(identity), 'access_token': 'private-access', 'refresh_token': 'private-refresh', 'expires_in': 3600}
        return dict(identity)
    monkeypatch.setattr(auth, 'auth_request', provider)
    monkeypatch.setattr(sessions, 'auth_request', provider)
    return client, db, user, identity, calls


def initiate(fixture):
    client, _, user, _, _ = fixture
    response = client.post('/api/v1/auth/forgot-password', json={'email': user.email})
    assert response.status_code == 200
    return client.cookies.get(cookie_name())


def test_default_email_uses_pkce_and_secure_server_cookie(recovery, monkeypatch):
    client, _, user, _, calls = recovery
    monkeypatch.setattr(settings, 'COOKIE_SECURE', True)
    initiate(recovery)
    header = client.cookies.get(cookie_name())
    payload = calls[-1][2]
    assert payload['email'] == user.email and payload['code_challenge_method'] == 's256'
    assert len(payload['code_challenge']) == 43
    state = json.loads(cipher().decrypt(header.encode()))
    assert state['purpose'] == 'recovery' and state['email'] == user.email
    assert len(state['verifier']) >= 43 and state['verifier'] not in header
    response = client.post('/api/v1/auth/forgot-password', json={'email': user.email})
    cookie = response.headers['set-cookie']
    assert all(item in cookie for item in ['HttpOnly', 'Secure', 'SameSite=lax', 'Path=/api/v1/auth', 'Max-Age=3600'])
    assert state['verifier'] not in response.text and 'same browser' in response.json()['message']


def test_desktop_recovery_cookie_can_use_cross_site_secure_policy(recovery, monkeypatch):
    client, _, user, _, _ = recovery
    monkeypatch.setattr(settings, 'COOKIE_SECURE', True)
    monkeypatch.setattr(settings, 'SESSION_COOKIE_SAMESITE', 'none')
    response = client.post('/api/v1/auth/forgot-password', json={'email': user.email})
    cookie = response.headers['set-cookie']
    assert response.status_code == 200
    assert all(item in cookie for item in ['HttpOnly', 'Secure', 'SameSite=none', 'Path=/api/v1/auth'])


def test_recovery_code_creates_restricted_session_then_password_change_revokes_it(recovery):
    client, db, _, _, calls = recovery
    initiate(recovery)
    response = client.post('/api/v1/auth/recovery/exchange', json={'code': 'valid-one-use-code'})
    assert response.status_code == 200 and response.json()['recovery'] is True
    assert 'private-access' not in response.text and 'private-refresh' not in response.text
    assert client.cookies.get(cookie_name()) is None
    raw = client.cookies.get(settings.SESSION_COOKIE_NAME)
    session = db.get(AuthSession, session_key(raw))
    assert session.recovery and 'private-access' not in session.access_token
    assert client.get('/api/v1/companies').status_code == 403
    assert client.post('/api/v1/auth/password', json={'password': 'UserChosenPassword!'}).status_code == 200
    assert db.get(AuthSession, session_key(raw)) is None
    assert any(method == 'PUT' and path == '/user' for method, path, _ in calls)


@pytest.mark.parametrize('state_kind', ['missing', 'tampered', 'expired', 'wrong-purpose'])
def test_invalid_browser_state_never_exchanges_or_grants_session(recovery, state_kind):
    client, db, user, _, calls = recovery
    if state_kind == 'tampered': value = 'not-an-authenticated-cookie'
    elif state_kind in {'expired', 'wrong-purpose'}:
        state = json.dumps({'email': user.email, 'verifier': 'v' * 64, 'purpose': 'login' if state_kind == 'wrong-purpose' else 'recovery'}).encode()
        value = cipher().encrypt_at_time(state, int(time.time()) - (3601 if state_kind == 'expired' else 0)).decode()
    else: value = None
    if value: client.cookies.set(cookie_name(), value, path='/api/v1/auth')
    response = client.post('/api/v1/auth/recovery/exchange', json={'code': 'valid-one-use-code'})
    assert response.status_code == 400 and 'same browser' in response.json()['detail']
    assert not calls and client.cookies.get(settings.SESSION_COOKIE_NAME) is None
    assert db.scalar(select(AuthSession).where(AuthSession.user_id == user.id)) is None


def test_code_from_other_account_cannot_grant_recovery(recovery):
    client, db, user, identity, _ = recovery
    initiate(recovery)
    identity['email'] = 'another@example.com'
    response = client.post('/api/v1/auth/recovery/exchange', json={'code': 'valid-one-use-code'})
    assert response.status_code == 401
    assert db.scalar(select(AuthSession).where(AuthSession.user_id == user.id)) is None


def test_unverified_account_cannot_grant_recovery(recovery):
    client, _, _, identity, _ = recovery
    initiate(recovery)
    identity['email_confirmed_at'] = None
    assert client.post('/api/v1/auth/recovery/exchange', json={'code': 'valid-one-use-code'}).status_code == 401
    assert client.cookies.get(settings.SESSION_COOKIE_NAME) is None


def test_invalid_and_replayed_code_cannot_grant_another_session(recovery):
    client, _, _, _, _ = recovery
    state = initiate(recovery)
    assert client.post('/api/v1/auth/recovery/exchange', json={'code': 'invalid-code'}).status_code == 401
    assert client.cookies.get(settings.SESSION_COOKIE_NAME) is None
    assert client.post('/api/v1/auth/recovery/exchange', json={'code': 'valid-one-use-code'}).status_code == 200
    client.cookies.clear()
    client.cookies.set(cookie_name(), state, path='/api/v1/auth')
    assert client.post('/api/v1/auth/recovery/exchange', json={'code': 'valid-one-use-code'}).status_code == 401
    assert client.cookies.get(settings.SESSION_COOKIE_NAME) is None


def test_client_tokens_and_callback_roles_cannot_request_recovery(recovery):
    client, _, _, _, calls = recovery
    for extra in [{'type': 'recovery'}, {'role': 'owner'}, {'access_token': 'untrusted'}]:
        assert client.post('/api/v1/auth/recovery/exchange', json={'code': 'valid-one-use-code', **extra}).status_code == 422
    assert not calls


def test_unsupported_provider_does_not_exchange(recovery, monkeypatch):
    client, _, _, _, calls = recovery
    monkeypatch.setattr(settings, 'AUTH_PROVIDER', 'legacy')
    assert client.post('/api/v1/auth/recovery/exchange', json={'code': 'valid-one-use-code'}).status_code == 400
    assert not calls
