"""Phase 4: real PostgreSQL transactions, mocked Supabase, existing tenant guards."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from fastapi import HTTPException
from tests.test_tenant_isolation import api, isolation_engine
from app.core.config import settings, Settings
from app.core.sessions import utcnow
from app.db.tenant_session import TenantSession
from app.models import User, Organization, Membership, Company, Role
from app.models.onboarding import SignupIntent, OrganizationProvision
from app.models.session import AuthSession
from app.models.tenant import TenantOwned
from app.models.workspace import WorkspaceSettings
from app.services import onboarding


@pytest.fixture
def business(api, monkeypatch):
    client, engine = api
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "supabase")
    monkeypatch.setattr(settings, "BUSINESS_REGISTRATION_ENABLED", True)
    identities = {i: {"id": f"00000000-0000-0000-0000-{i:012d}", "email": f"user{i}@example.com",
                       "email_confirmed_at": "2026-10-16T00:00:00Z"} for i in range(1, 5)}
    with Session(engine) as db:
        for uid in (1, 2, 3): db.get(User, uid).auth_user_id = identities[uid]["id"]
        db.commit()
    calls = []
    def provider(method, path, data=None, token=None, **kwargs):
        calls.append((method, path))
        if path == "/user": return dict(identities[int(token.split('-')[-1])])
        if path.startswith('/signup'):
            return {"user": {**identities[4], "email_confirmed_at": None}, "session": None}
        if path.startswith('/token'):
            uid = int(data['email'].split('@')[0].replace('user', ''))
        elif path == '/verify': uid = 4
        else: raise AssertionError(path)
        return {"user": dict(identities[uid]), "access_token": f"access-{uid}", "refresh_token": f"refresh-{uid}", "expires_in": 3600}
    from app.api.routes import auth
    from app.core import sessions
    for module in (auth, sessions, onboarding): monkeypatch.setattr(module, "auth_request", provider)
    def login(uid):
        result = client.post('/api/v1/auth/login', data={"username": f"user{uid}@example.com", "password": "fixture-password"})
        assert result.status_code == 200, result.text
    return client, engine, login, identities, calls


def details(name="New Business", key=None):
    return {"name": name, "request_key": key or str(uuid4())}


def test_verified_signup_then_empty_workspace_and_correct_owner(business):
    client, engine, login, _, calls = business
    body={"name":"New Owner","email":"user4@example.com","password":"secure-password-123"}
    for _ in range(2):
        response=client.post('/api/v1/auth/business-signup',json=body)
        assert response.status_code==200,response.text
        assert 'access_token' not in response.text and 'password' not in response.text
    with Session(engine) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(SignupIntent))==1
        assert db.scalar(sa.select(User).where(User.email==body['email'])) is None
        assert db.scalar(sa.select(sa.func.count()).select_from(Organization))==2
    response=client.post('/api/v1/auth/recovery/verify',json={"token_hash":"verified-signup-hash","type":"signup"})
    assert response.status_code==200 and response.json()['recovery'] is False
    response=client.post('/api/v1/auth/onboarding',json=details())
    assert response.status_code==200,response.text
    org=response.json()['organization_id']
    assert client.get('/api/v1/auth/me').json()['organization_role']=='owner'
    assert client.get('/api/v1/companies').json()['items']==[]
    with Session(engine) as db:
        user=db.scalar(sa.select(User).where(User.email==body['email']))
        assert user.role.name=='viewer'  # No global elevation.
        member=db.scalar(sa.select(Membership).where(Membership.organization_id==org))
        assert member.user_id==user.id and member.role=='owner' and member.permission_role_name=='admin'
        for mapper in TenantOwned.__subclasses__():
            if mapper is WorkspaceSettings: continue
            assert db.scalar(sa.select(sa.func.count()).select_from(mapper).where(mapper.organization_id==org))==0
        assert db.scalar(sa.select(WorkspaceSettings).where(WorkspaceSettings.organization_id==org)).name=='New Business'
        assert db.get(Membership,1).role=='admin'  # Existing memberships untouched.


def test_two_creators_are_isolated_and_roles_preserved(business):
    client,engine,login,_,_=business
    login(3)
    a=client.post('/api/v1/auth/onboarding',json=details("Business A")).json()['organization_id']
    assert client.post('/api/v1/companies',json={"name":"Private A"}).status_code==200
    login(2)
    b=client.post('/api/v1/auth/onboarding',json=details("Business B")).json()['organization_id']
    assert a!=b and client.get('/api/v1/companies').json()['items']==[]
    assert client.get('/api/v1/companies',headers={"X-Organization-ID":str(a)}).status_code==403
    assert client.post('/api/v1/auth/organization',json={"organization_id":a}).status_code==403
    assert client.post('/api/v1/auth/organization',json={"organization_id":2}).status_code==200
    assert client.get('/api/v1/auth/me').json()['organization_role']=='admin'
    assert client.post('/api/v1/auth/organization',json={"organization_id":b}).status_code==200
    assert client.get('/api/v1/auth/me').json()['organization_role']=='owner'
    with Session(engine) as db:
        assert db.get(User,2).role.name=='admin'
        assert db.scalar(sa.select(Membership.role).where(Membership.user_id==2,Membership.organization_id==2))=='admin'


def test_retry_is_idempotent_and_rejects_changed_payload(business):
    client,engine,login,_,_=business
    login(3); body=details()
    first=client.post('/api/v1/auth/onboarding',json=body)
    assert first.status_code==200,first.text
    assert client.post('/api/v1/auth/onboarding',json=body).json()==first.json()
    assert client.post('/api/v1/auth/onboarding',json={**body,"name":"Different"}).status_code==409
    with Session(engine) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(Organization))==3
        assert db.scalar(sa.select(sa.func.count()).select_from(OrganizationProvision))==1


@pytest.mark.parametrize('failure',['unverified','recovery','inactive','disabled','legacy'])
def test_unverified_or_ineligible_creator_denied(business,monkeypatch,failure):
    client,engine,login,identities,_=business
    login(3)
    if failure=='unverified': identities[3]['email_confirmed_at']=None
    if failure=='recovery':
        with Session(engine) as db:
            for s in db.scalars(sa.select(AuthSession)):s.recovery=True
            db.commit()
    if failure=='inactive':
        with Session(engine) as db: db.get(User,3).is_active=False;db.commit()
    if failure=='disabled':monkeypatch.setattr(settings,'BUSINESS_REGISTRATION_ENABLED',False)
    if failure=='legacy':monkeypatch.setattr(settings,'AUTH_PROVIDER','legacy')
    assert client.post('/api/v1/auth/onboarding',json=details()).status_code in {401,403}
    with Session(engine) as db:assert db.scalar(sa.select(sa.func.count()).select_from(Organization))==2


def test_unverified_signup_cannot_login_or_create_user(business):
    client,engine,_,identities,_=business
    client.post('/api/v1/auth/business-signup',json={"name":"New","email":"user4@example.com","password":"secure-password-123"})
    identities[4]['email_confirmed_at']=None
    assert client.post('/api/v1/auth/login',data={"username":"user4@example.com","password":"secure-password-123"}).status_code==401
    with Session(engine) as db:assert db.scalar(sa.select(User.id).where(User.email=='user4@example.com')) is None


def test_signup_preserves_existing_account_and_hides_existence(business):
    client,engine,_,_,calls=business
    before=list(calls)
    result=client.post('/api/v1/auth/business-signup',json={"name":"Changed","email":"user1@example.com","password":"secure-password-123"})
    assert result.status_code==200 and calls==before
    with Session(engine) as db:
        assert db.get(User,1).name=='User 1'
        assert db.scalar(sa.select(sa.func.count()).select_from(SignupIntent))==0


def test_revoked_receipt_does_not_restore_access(business):
    client,engine,login,_,_=business
    login(3); body=details()
    org=client.post('/api/v1/auth/onboarding',json=body).json()['organization_id']
    with Session(engine) as db:
        db.scalar(sa.select(Membership).where(Membership.organization_id==org)).is_active=False;db.commit()
    assert client.get('/api/v1/companies').status_code==403
    assert client.post('/api/v1/auth/organization',json={"organization_id":org}).status_code==403
    assert client.post('/api/v1/auth/onboarding',json=body).status_code==403
    assert client.get('/api/v1/auth/organizations').json()==[]


@pytest.mark.parametrize('injection',[{"role":"owner"},{"organization_id":1},{"owner_id":1}])
def test_frontend_cannot_target_legacy_or_grant_roles(business,injection):
    client,engine,login,_,_=business
    login(3)
    assert client.post('/api/v1/auth/onboarding',json={**details(),**injection}).status_code==422
    with Session(engine) as db:assert db.scalar(sa.select(sa.func.count()).select_from(Organization))==2


def test_failure_rolls_back_org_owner_settings_and_session(business):
    client,engine,login,_,_=business
    login(3)
    def fail(db,*args):
        if any(isinstance(obj,WorkspaceSettings) for obj in db.new):raise HTTPException(503,'Injected provisioning failure')
    sa.event.listen(TenantSession,'before_flush',fail)
    try:assert client.post('/api/v1/auth/onboarding',json=details()).status_code==503
    finally:sa.event.remove(TenantSession,'before_flush',fail)
    with Session(engine) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(Organization))==2
        assert db.scalar(sa.select(sa.func.count()).select_from(OrganizationProvision))==0
        assert db.scalar(sa.select(Membership).where(Membership.user_id==3)) is None
        assert db.scalar(sa.select(AuthSession).where(AuthSession.user_id==3)).active_organization_id is None
    assert client.post('/api/v1/auth/onboarding',json=details()).status_code==200


def test_duplicate_slug_safely_retries(business,monkeypatch):
    client,engine,login,_,_=business
    with Session(engine) as db:db.add(Organization(name='Unrelated',slug='new-business-collision'));db.commit()
    suffixes=iter(['collision','unique'])
    monkeypatch.setattr(onboarding.secrets,'token_hex',lambda _:next(suffixes))
    login(3)
    result=client.post('/api/v1/auth/onboarding',json=details())
    assert result.status_code==200,result.text
    with Session(engine) as db:assert db.get(Organization,result.json()['organization_id']).slug=='new-business-unique'


def test_concurrent_retries_create_exactly_one_owner(business):
    _,engine,_,_,_=business
    with Session(engine) as db:
        for i in range(2):db.add(AuthSession(id=f'concurrent-{i}',user_id=3,expires_at=utcnow()+timedelta(hours=1)))
        db.commit()
    key=str(uuid4())
    def run(i):
        with TenantSession(engine,autoflush=False) as db:
            return onboarding.create_workspace(db,db.get(User,3),db.get(AuthSession,f'concurrent-{i}'),'Concurrent',key)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
    assert results[0]==results[1]
    with Session(engine) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(OrganizationProvision))==1
        assert db.scalar(sa.select(sa.func.count()).select_from(Membership).where(Membership.user_id==3))==1


def test_default_and_production_rollout_gate(monkeypatch):
    config=Settings(_env_file=None,DATABASE_URL='postgresql://unused/test',JWT_SECRET_KEY='x'*40)
    assert config.BUSINESS_REGISTRATION_ENABLED is False and config.AUTH_EMAIL_CONFIGURATION_VERIFIED is False
    monkeypatch.setattr(settings,'ENVIRONMENT','production')
    monkeypatch.setattr(settings,'AUTH_PROVIDER','supabase')
    monkeypatch.setattr(settings,'TENANT_ISOLATION_ENABLED',True)
    monkeypatch.setattr(settings,'BUSINESS_REGISTRATION_ENABLED',True)
    monkeypatch.setattr(settings,'AUTH_EMAIL_CONFIGURATION_VERIFIED',False)
    assert onboarding.registration_enabled() is False


def test_existing_multi_workspace_login_skips_onboarding_and_preserves_viewer(business):
    client,engine,login,_,_=business
    login(1)
    assert len(client.get('/api/v1/auth/organizations').json())==2
    assert client.post('/api/v1/auth/organization',json={"organization_id":2}).status_code==200
    assert client.get('/api/v1/auth/me').json()['organization_role']=='viewer'
    assert client.post('/api/v1/companies',json={"name":"Forbidden"}).status_code==403
    with Session(engine) as db: assert db.scalar(sa.select(sa.func.count()).select_from(OrganizationProvision))==0


@pytest.mark.parametrize('failure',['provider','auto_confirm','malformed'])
def test_signup_failure_grants_no_account_or_membership(business,monkeypatch,failure):
    client,engine,_,identities,_=business
    from app.api.routes import auth
    def provider(*args,**kwargs):
        if failure=='provider':raise HTTPException(503,'Unavailable')
        if failure=='auto_confirm':return {'user':identities[4],'access_token':'must-not-leak'}
        return {'user':{'id':'invalid','email':'user4@example.com'}}
    monkeypatch.setattr(auth,'auth_request',provider)
    response=client.post('/api/v1/auth/business-signup',json={'name':'New','email':'user4@example.com','password':'secure-password-123'})
    assert response.status_code in {502,503} and 'must-not-leak' not in response.text
    with Session(engine) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(SignupIntent))==0
        assert db.scalar(sa.select(sa.func.count()).select_from(User))==3
        assert db.scalar(sa.select(sa.func.count()).select_from(Organization))==2


def test_idempotency_key_is_bound_to_creator_and_new_dashboard_is_empty(business):
    client,engine,login,_,_=business
    body=details('Same business name')
    login(3)
    a=client.post('/api/v1/auth/onboarding',json=body).json()['organization_id']
    summary=client.get('/api/v1/dashboard/summary')
    assert summary.status_code==200,summary.text
    assert summary.json()['total_deals']==summary.json()['total_companies']==0
    login(2)
    b=client.post('/api/v1/auth/onboarding',json=body).json()['organization_id']
    assert a!=b
    with Session(engine) as db:assert db.get(Organization,a).slug!=db.get(Organization,b).slug


@pytest.mark.parametrize('failure',['session_revoked','session_expired','account_disabled'])
def test_provisioning_rechecks_account_and_session_under_lock(business,failure):
    _,engine,_,_,_=business
    with Session(engine) as db:
        db.add(AuthSession(id='checked-session',user_id=3,expires_at=utcnow()+timedelta(hours=1)));db.commit()
    with TenantSession(engine,autoflush=False) as db:
        user=db.get(User,3);session=db.get(AuthSession,'checked-session')
        with Session(engine) as other:
            if failure=='session_revoked':other.delete(other.get(AuthSession,'checked-session'))
            elif failure=='session_expired':other.get(AuthSession,'checked-session').expires_at=utcnow()-timedelta(seconds=1)
            else:other.get(User,3).is_active=False
            other.commit()
        with pytest.raises(HTTPException):onboarding.create_workspace(db,user,session,'Denied',str(uuid4()))
    with Session(engine) as db:assert db.scalar(sa.select(sa.func.count()).select_from(Organization))==2
