from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from datetime import timedelta
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from fastapi import HTTPException
from tests.test_platform_admin import control,business,api,isolation_engine
from tests.test_tenant_isolation import FIXTURE_PASSWORD_HASH
from app.models import User,Membership,Role,Organization,WorkflowRun
from app.models.subscription import SubscriptionPlan,Subscription
from app.models.invitation import OrganizationInvitation
from app.db.tenant_session import TenantSession
from app.services import team
from app.core.sessions import utcnow

def plan_body(seats=2,**kwargs):
    return dict(name='Starter',currency='USD',price=None,billing_interval='month',seat_limit=seats,entitlements={'analytics':True,'exports':False,'attachments':False,'workflows':False},published=True,reason='Explicit test configuration',**kwargs)

@pytest.fixture
def foundation(control,monkeypatch):
    client,engine,login,identities=control
    response=client.put('/api/v1/platform/plans/starter',json=plan_body())
    assert response.status_code==200,response.text
    pid=response.json()['id']
    calls=[]
    def send(email,name,existing):
        calls.append(email)
        return existing['auth_user_id'] if existing and existing['auth_user_id'] else '00000000-0000-0000-0000-000000000004'
    monkeypatch.setattr(team,'send_invitation',send)
    with Session(engine) as db:
        role=db.scalar(sa.select(Role.id).where(Role.name=='sales_rep'))
        for uid in (4,5):
            db.add(User(id=uid,name=f'Rep {uid}',email=f'rep{uid}@example.com',password_hash=FIXTURE_PASSWORD_HASH,role_id=role,is_active=True,auth_user_id=f'00000000-0000-0000-0000-{uid:012d}'));db.flush()
            db.add(Membership(organization_id=1,user_id=uid,role='sales_rep',is_active=False))
        db.commit()
    return client,engine,login,pid,calls

def assign(client,pid,org=1,**overrides):
    return client.put(f'/api/v1/platform/subscriptions/{org}',json={'plan_id':pid,'status':'active','enforcement_enabled':True,'reason':'Explicit test subscription',**overrides})

def test_unconfigured_customers_keep_access_and_prices_are_not_invented(foundation):
    client,engine,login,pid,_=foundation
    login(1)
    response=client.get('/api/v1/subscription',headers={'X-Organization-ID':'1'})
    assert response.status_code==200 and response.json()['subscription'] is None
    assert all(response.json()['entitlements'].values()) and response.json()['billing_available'] is False
    plans=client.get('/api/v1/subscription/plans',headers={'X-Organization-ID':'1'}).json()
    assert len(plans)==1 and plans[0]['id']==pid and plans[0]['price'] is None
    assert client.get('/api/v1/exports/companies',headers={'X-Organization-ID':'1'}).status_code==200

def test_only_platform_admin_may_configure_plans_and_subscription(foundation):
    client,_,login,pid,_=foundation
    login(1)
    assert client.put('/api/v1/platform/plans/business',json=plan_body()).status_code==403
    assert assign(client,pid).status_code==403
    assert client.put('/api/v1/subscription',json={'plan_id':pid,'status':'active'}).status_code==405

def test_subscriptions_scoped_entitlements_and_suspension(foundation):
    client,_,login,pid,_=foundation
    assert assign(client,pid,external_customer_id='private-provider-id').status_code==200
    login(1)
    a=client.get('/api/v1/subscription?organization_id=2',headers={'X-Organization-ID':'1'}).json()
    assert a['subscription']['enforcement_enabled'] and 'private-provider-id' not in str(a)
    b=client.get('/api/v1/subscription',headers={'X-Organization-ID':'2'}).json()
    assert b['subscription'] is None
    assert client.get('/api/v1/exports/companies',headers={'X-Organization-ID':'1'}).status_code==403
    assert client.get('/api/v1/attachments/1/content',headers={'X-Organization-ID':'1'}).status_code==403
    assert client.get('/api/v1/dashboard/summary',headers={'X-Organization-ID':'1'}).status_code==200
    assert client.get('/api/v1/companies',headers={'X-Organization-ID':'999'}).status_code==403
    login(3);assert client.put('/api/v1/platform/organizations/1',json={'is_suspended':True,'reason':'Review'}).status_code==200
    login(1);assert client.get('/api/v1/subscription',headers={'X-Organization-ID':'1'}).status_code==403

def test_invitation_reserves_seat_acceptance_consumes_it_and_role_changes_cannot_bypass(foundation):
    client,engine,login,pid,calls=foundation
    assert assign(client,pid).status_code==200
    login(1);h={'X-Organization-ID':'1'}
    invitation=client.post('/api/v1/team/invitations',headers=h,json={'name':'Existing user','email':'user2@example.com','role':'sales_rep'})
    assert invitation.status_code==200,invitation.text
    assert client.post('/api/v1/team/invitations',headers=h,json={'name':'Other','email':'other@example.com'}).status_code==409
    assert len(calls)==1
    assert client.put('/api/v1/team/members/4',headers=h,json={'is_active':True,'role':'viewer'}).status_code==409
    login(2)
    assert client.post(f"/api/v1/auth/invitations/{invitation.json()['id']}/accept").status_code==200
    login(1)
    data=client.get('/api/v1/subscription',headers=h).json()
    assert data['seats']=={'active':2,'pending':0,'limit':2}
    assert client.put('/api/v1/team/members/4',headers=h,json={'is_active':True,'role':'sales_manager'}).status_code==409
    assert client.patch('/api/v1/users/4/status?is_active=true',headers=h).status_code==409

def test_acceptance_revalidates_capacity_when_pending_invites_preexist(foundation):
    client,engine,login,pid,_=foundation
    with Session(engine) as db:
        db.add(OrganizationInvitation(organization_id=1,email='user2@example.com',name='Existing',role='sales_rep',status='pending',invited_by=1,provider_user_id=db.get(User,2).auth_user_id,expires_at=utcnow()+timedelta(days=1)));db.commit()
        invitation=db.scalar(sa.select(OrganizationInvitation.id))
    assert assign(client,pid).status_code==200
    with Session(engine) as db:
        db.add(OrganizationInvitation(organization_id=1,email='user3@example.com',name='Historical extra',role='viewer',status='pending',invited_by=1,provider_user_id=db.get(User,3).auth_user_id,expires_at=utcnow()+timedelta(days=1)));db.commit()
    login(2)
    assert client.post(f'/api/v1/auth/invitations/{invitation}/accept').status_code==409
    with Session(engine) as db:assert db.scalar(sa.select(Membership).where(Membership.organization_id==1,Membership.user_id==2)) is None

@pytest.mark.parametrize('operation',['invite','activate','mixed'])
def test_concurrent_admissions_share_one_remaining_seat(foundation,operation):
    client,engine,_,pid,_=foundation
    assert assign(client,pid).status_code==200
    def run(uid):
        with TenantSession(engine,autoflush=False) as db:
            db.info.update(organization_id=1,actor_id=1)
            try:
                if operation=='invite' or (operation=='mixed' and uid==4):team.invite(db,SimpleNamespace(id=1),f'Rep {uid}',f'rep{uid}@example.com','sales_rep')
                else:team.change_member(db,SimpleNamespace(id=1),uid,is_active=True,role='viewer')
                db.commit();return 200
            except HTTPException as error:db.rollback();return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(run,[4,5]))==[200,409]
    from app.services.subscriptions import usage
    with Session(engine) as db:assert sum(usage(db,1))==2

def test_plan_downgrade_rejected_and_failed_changes_rollback(foundation):
    client,engine,login,pid,_=foundation
    assert assign(client,pid).status_code==200
    login(1)
    assert client.put('/api/v1/team/members/4',headers={'X-Organization-ID':'1'},json={'is_active':True}).status_code==200
    login(3)
    assert client.put('/api/v1/platform/plans/starter',json=plan_body(1)).status_code==409
    with Session(engine) as db:assert db.get(SubscriptionPlan,pid).seat_limit==2
    response=client.put('/api/v1/platform/plans/business',json=plan_body(1));assert response.status_code==200
    assert assign(client,response.json()['id']).status_code==409
    with Session(engine) as db:assert db.scalar(sa.select(Subscription.plan_id).where(Subscription.organization_id==1))==pid

@pytest.mark.parametrize('status',['paused','expired','canceled'])
def test_inactive_subscription_denies_optional_features_but_preserves_core_crm(foundation,status):
    client,_,login,pid,_=foundation
    assert assign(client,pid,status=status).status_code==200
    login(1);h={'X-Organization-ID':'1'}
    assert client.get('/api/v1/dashboard/summary',headers=h).status_code==403
    assert client.get('/api/v1/companies',headers=h).status_code==200
    assert client.get('/api/v1/subscription',headers=h).status_code==200
    assert client.put('/api/v1/team/members/4',headers=h,json={'is_active':True}).status_code==403

def test_disabled_enforcement_and_unpublished_plans(foundation):
    client,_,login,pid,_=foundation
    assert assign(client,pid,enforcement_enabled=False,status='paused').status_code==200
    body=plan_body();body['published']=False
    assert client.put('/api/v1/platform/plans/starter',json=body).status_code==200
    login(1);h={'X-Organization-ID':'1'}
    assert client.get('/api/v1/subscription/plans',headers=h).json()==[]
    assert client.get('/api/v1/exports/companies',headers=h).status_code==200
    assert client.put('/api/v1/team/members/4',headers=h,json={'is_active':True}).status_code==200

def test_invalid_plan_and_subscription_inputs(foundation):
    client,_,_,pid,_=foundation
    for changes in ({'price':'-1'},{'seat_limit':0},{'entitlements':{'unknown':True}},{'entitlements':{'exports':'false'}}):
        body=plan_body();body.update(changes)
        assert client.put('/api/v1/platform/plans/business',json=body).status_code==422
    assert assign(client,pid,ends_at='2000-01-01T00:00:00Z').status_code==422

def test_workflow_entitlement_applies_to_automatic_execution(foundation):
    client,engine,login,pid,_=foundation
    assert assign(client,pid).status_code==200
    login(1)
    response=client.post('/api/v1/leads',headers={'X-Organization-ID':'1'},json={'title':'Qualified prospect','status':'qualified'})
    assert response.status_code==200,response.text
    with Session(engine) as db:assert db.scalar(sa.select(sa.func.count()).select_from(WorkflowRun).where(WorkflowRun.organization_id==1))==0

def test_concurrent_acceptances_consume_distinct_reserved_seats(foundation):
    client,engine,login,pid,_=foundation
    assert client.put('/api/v1/platform/plans/starter',json=plan_body(3)).status_code==200
    assert assign(client,pid).status_code==200
    login(1);ids=[]
    for email in ('user2@example.com','rep4@example.com'):
        result=client.post('/api/v1/team/invitations',headers={'X-Organization-ID':'1'},json={'name':'Recipient','email':email,'role':'sales_rep'})
        assert result.status_code==200,result.text
        ids.append(result.json()['id'])
    from app.api.routes.team import accept
    def run(pair):
        iid,uid=pair
        with TenantSession(engine,autoflush=False) as db:
            return accept(iid,db,db.get(User,uid))
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run,zip(ids,[2,4])))==[{'organization_id':1},{'organization_id':1}]
    from app.services.subscriptions import usage
    with Session(engine) as db:assert usage(db,1)==(3,0)

def test_expired_reservations_release_seats(foundation):
    client,engine,login,pid,_=foundation
    assert assign(client,pid).status_code==200
    with Session(engine) as db:
        db.add(OrganizationInvitation(organization_id=1,email='expired@example.com',name='Expired',role='viewer',status='pending',invited_by=1,provider_user_id='00000000-0000-0000-0000-000000000099',expires_at=utcnow()-timedelta(seconds=1)));db.commit()
    login(1)
    assert client.put('/api/v1/team/members/4',headers={'X-Organization-ID':'1'},json={'is_active':True}).status_code==200

def test_owner_cannot_self_upgrade_and_three_plan_codes_are_configurable(foundation):
    client,engine,login,pid,_=foundation
    for code,name in [('business','Business'),('enterprise','Enterprise')]:
        body=plan_body();body['name']=name
        assert client.put('/api/v1/platform/plans/'+code,json=body).status_code==200
    with Session(engine) as db:
        member=db.scalar(sa.select(Membership).where(Membership.organization_id==1,Membership.user_id==1));member.role='owner';member.permission_role_name='admin';db.commit()
    login(1)
    assert len(client.get('/api/v1/subscription/plans',headers={'X-Organization-ID':'1'}).json())==3
    assert assign(client,pid).status_code==403
