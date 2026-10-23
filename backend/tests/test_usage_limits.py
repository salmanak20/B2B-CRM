"""PostgreSQL quotas, aggregate privacy, pending invitations and MFA boundaries."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from tests.test_free_pilot import pilot, foundation, control, business, api, isolation_engine, approve
from app.models import Company, Membership, Subscription, WorkflowRun, Lead
from app.models.usage import ResourceTotal, ResourceDay, WorkflowPeriod
from app.models.invitation import OrganizationInvitation
from app.models.session import AuthSession
from app.models.platform import PlatformAudit
from app.core.config import settings
from app.core.sessions import utcnow, encrypt, decrypt
from app.services.usage import PILOT_LIMITS


def configure(client, **changes):
    old=client.get('/api/v1/platform/organizations/1/limits').json()['limits']
    return client.put('/api/v1/platform/organizations/1/limits',json={'limits':{**PILOT_LIMITS,**changes},'expected_limits':old,'reason':'Explicit isolated test quota'})


def test_new_pilot_defaults_and_existing_plan_unchanged(pilot):
    client,engine,_,pid,_=pilot
    assert approve(client,pid).status_code==200
    result=client.get('/api/v1/platform/organizations/1/limits').json()
    assert result['limits']==PILOT_LIMITS
    assert result['consumption']['companies']['used']==1
    aggregate=client.get('/api/v1/platform/usage-summary')
    assert aggregate.status_code==200,aggregate.text
    assert aggregate.json()['owners']==1
    with Session(engine) as db:
        assert db.scalar(sa.select(Subscription).where(Subscription.organization_id==1)).resource_limits==PILOT_LIMITS
    assert client.get('/api/v1/platform/plans').json()[-1]['seat_limit']==5


@pytest.mark.parametrize('table,resource',[('companies','companies'),('leads','leads'),('contacts','contacts'),('deals','deals'),('tasks','tasks'),('attachments','storage_bytes')])
def test_direct_database_writes_cannot_bypass_quotas(pilot,table,resource):
    client,engine,_,pid,_=pilot
    assert approve(client,pid).status_code==200
    assert configure(client,**{resource:10 if table=='attachments' else 1}).status_code==200
    from app.db.session import Base
    target=Base.metadata.tables[table]
    with engine.connect() as db:
        values=dict(db.execute(sa.select(target).where(target.c.organization_id==1)).mappings().first())
        values.pop('id');values.pop('created_at',None)
        if table=='attachments': values['storage_path']='quota-denied-path'
    with pytest.raises(IntegrityError,match='CRM_QUOTA:'):
        with engine.begin() as db: db.execute(target.insert().values(**values))
    assert client.get('/api/v1/platform/organizations/1/usage').json()['resources'][resource]['used']==(10 if table=='attachments' else 1)


def test_concurrent_allocations_and_safe_decrease(pilot):
    client,engine,login,pid,_=pilot
    approve(client,pid)
    assert configure(client,companies=2).status_code==200
    def allocate(i):
        try:
            with engine.begin() as db:
                db.execute(Company.__table__.insert().values(organization_id=1,owner_id=1,name='Concurrent '+str(i)))
            return True
        except IntegrityError as error:
            assert 'CRM_QUOTA:companies' in str(error.orig)
            return False
    with ThreadPoolExecutor(max_workers=5) as executor: assert sum(executor.map(allocate,range(5)))==1
    assert configure(client,companies=0).status_code==200
    login(1)
    result=client.post('/api/v1/companies',headers={'X-Organization-ID':'1'},json={'name':'Blocked through API'})
    assert result.status_code==409 and 'limit reached' in result.text
    data=client.get('/api/v1/subscription/usage',headers={'X-Organization-ID':'1'}).json()
    assert data['resources']['companies']==dict(used=2,limit=0,remaining=0,percent=100)
    assert client.put('/api/v1/companies/1',headers={'X-Organization-ID':'1'},json={'name':'Retained record editable'}).status_code==200
    assert client.get('/api/v1/companies',headers={'X-Organization-ID':'2'}).json()['total']==1


def test_stale_quota_update_and_platform_audit(pilot):
    client,engine,_,pid,_=pilot;approve(client,pid)
    assert configure(client,seats=10,leads=2000).status_code==200
    result=client.put('/api/v1/platform/organizations/1/limits',json={'limits':PILOT_LIMITS,'expected_limits':PILOT_LIMITS,'reason':'Stale request'})
    assert result.status_code==409
    with Session(engine) as db:
        entry=db.scalar(sa.select(PlatformAudit).where(PlatformAudit.action=='quotas_changed'))
        assert 'previous=' in entry.reason and '2000' in entry.reason
    assert client.get('/api/v1/platform/subscriptions/1').json()['seats']['limit']==10
    # Reapplying the fixed base plan must preserve the approved ten-seat override.
    with engine.begin() as db:
        for i in range(6):
            db.execute(OrganizationInvitation.__table__.insert().values(organization_id=1,name='Pending recipient',email=f'pending{i}@example.com',role='viewer',status='pending',invited_by=1,provider_user_id=None,expires_at=utcnow()+timedelta(days=7)))
    from app.services.subscriptions import pilot_definition
    assert client.put('/api/v1/platform/plans/free_pilot',json={**pilot_definition(),'reason':'Idempotent base plan review'}).status_code==200


def test_usage_history_counts_writes_without_private_contents(pilot):
    client,engine,login,pid,_=pilot;approve(client,pid)
    with engine.begin() as db:
        db.execute(Company.__table__.insert().values(organization_id=1,owner_id=1,name='NeverExposeCustomerName'))
    result=client.get('/api/v1/platform/organizations/1/usage?days=7&interval=week')
    assert result.status_code==200 and 'NeverExposeCustomerName' not in result.text and 'Tenant1Only' not in result.text
    data=result.json();assert data['history_started_at'] and data['last_recorded_activity'] and data['api_requests'] is None
    assert data['resources']['companies']['used']==2
    assert any(row['resource']=='companies' and row['created']==2 for row in data['trends'])
    login(1)
    assert client.get('/api/v1/platform/organizations/1/usage').status_code==403
    assert client.put('/api/v1/platform/organizations/1/limits',json={'limits':PILOT_LIMITS,'expected_limits':PILOT_LIMITS,'reason':'Forbidden'}).status_code==403
    own=client.get('/api/v1/subscription/usage',headers={'X-Organization-ID':'1'}).json()
    assert own['organization_id']==1


@pytest.mark.parametrize('cleanup_available',[False,True])
def test_storage_quota_reserved_before_upload_and_failure_releases(pilot,monkeypatch,cleanup_available):
    client,engine,login,pid,_=pilot;approve(client,pid)
    configure(client,storage_bytes=10)
    from app.api.routes import attachments
    calls=[]
    monkeypatch.setattr(attachments,'storage',lambda *a,**k:calls.append(a) or {})
    login(1)
    path='/api/v1/records/companies/1/attachments'
    result=client.post(path,headers={'X-Organization-ID':'1'},files={'file':('test.txt',b'x','text/plain')})
    assert result.status_code==409 and calls==[]
    login(3);configure(client,storage_bytes=20);login(1)
    from fastapi import HTTPException
    def unavailable(method,*a,**k):
        if method=='DELETE' and cleanup_available:return {}
        raise HTTPException(503,'Storage unavailable')
    monkeypatch.setattr(attachments,'storage',unavailable)
    assert client.post(path,headers={'X-Organization-ID':'1'},files={'file':('test.txt',b'x','text/plain')}).status_code==503
    assert client.get('/api/v1/subscription/usage',headers={'X-Organization-ID':'1'}).json()['resources']['storage_bytes']['used']==(10 if cleanup_available else 11)
    if not cleanup_available:
        from app.models.workspace import Attachment
        with Session(engine) as db:
            pending=db.scalar(sa.select(Attachment.id).where(Attachment.upload_state=='pending'))
        assert client.get(f'/api/v1/attachments/{pending}/download',headers={'X-Organization-ID':'1'}).status_code==409
        monkeypatch.setattr(attachments,'storage',lambda *a,**k:{})
        assert client.delete(f'/api/v1/attachments/{pending}',headers={'X-Organization-ID':'1'}).status_code==200
        assert client.get('/api/v1/subscription/usage',headers={'X-Organization-ID':'1'}).json()['resources']['storage_bytes']['used']==10


def test_workflow_consumption_survives_record_deletion(pilot):
    client,engine,_,pid,_=pilot;approve(client,pid);configure(client,workflow_executions=1)
    with engine.begin() as db:
        rid=db.scalar(WorkflowRun.__table__.insert().values(organization_id=1,rule_id=1,lead_id=1,task_id=1).returning(WorkflowRun.id))
    with engine.begin() as db:db.execute(WorkflowRun.__table__.delete().where(WorkflowRun.id==rid))
    with pytest.raises(IntegrityError,match='CRM_QUOTA:workflow_executions'):
        with engine.begin() as db:db.execute(WorkflowRun.__table__.insert().values(organization_id=1,rule_id=1,lead_id=1,task_id=1))
    assert client.get('/api/v1/platform/organizations/1/usage').json()['resources']['workflow_executions']['used']==1
    previous=client.get('/api/v1/platform/subscriptions/1').json()['subscription']['ends_at']
    assert approve(client,pid,pilot_action='extend',expected_ends_at=previous).status_code==200
    with engine.begin() as db:db.execute(WorkflowRun.__table__.insert().values(organization_id=1,rule_id=1,lead_id=1,task_id=1))
    with Session(engine) as db:assert db.scalar(sa.select(sa.func.sum(WorkflowPeriod.executions)))==2


def test_manual_registration_verified_owner_idempotent_and_suspended(control):
    client,engine,login,ids=control
    body=dict(name='Approved existing owner business',owner_id=2,request_key=str(uuid4()),reason='Exact test approval')
    result=client.post('/api/v1/platform/organizations',json=body)
    assert result.status_code==200,result.text
    org=result.json()['organization_id']
    assert client.post('/api/v1/platform/organizations',json=body).json()['organization_id']==org
    with Session(engine) as db:
        from app.models import Organization,User
        assert db.get(Organization,org).is_suspended
        assert db.scalar(sa.select(Membership).where(Membership.organization_id==org)).role=='owner'
        assert db.get(User,2).role.name=='admin'
    ids[1]['email_confirmed_at']=None
    assert client.post('/api/v1/platform/organizations',json={**body,'owner_id':1,'request_key':str(uuid4())}).status_code==422
    login(2)
    assert client.get('/api/v1/companies',headers={'X-Organization-ID':str(org)}).status_code==403


def test_no_smtp_new_identity_stays_pending_without_provider_call(pilot,monkeypatch):
    client,engine,login,pid,_=pilot;approve(client,pid)
    monkeypatch.setattr(settings,'AUTH_EMAIL_CONFIGURATION_VERIFIED',False)
    from app.services import team
    monkeypatch.setattr(team,'auth_request',lambda *a,**k:pytest.fail('New identity must not call provider'))
    login(1)
    result=client.post('/api/v1/team/invitations',headers={'X-Organization-ID':'1'},json={'name':'Pending recipient','email':'new-recipient@example.com','role':'viewer'})
    assert result.status_code==200,result.text
    assert result.json()['delivery_available'] is False and result.json()['acceptance_available'] is False
    with Session(engine) as db:
        row=db.scalar(sa.select(OrganizationInvitation).where(OrganizationInvitation.email=='new-recipient@example.com'))
        assert row.provider_user_id is None and row.status=='pending'
    assert client.get('/api/v1/team/members',headers={'X-Organization-ID':'1'}).json()['seats']['used']==2


def test_no_smtp_existing_verified_recipient_accepts_after_sign_in(pilot,monkeypatch):
    client,engine,login,pid,identities=pilot;approve(client,pid)
    monkeypatch.setattr(settings,'AUTH_EMAIL_CONFIGURATION_VERIFIED',False)
    from app.services import team
    calls=[]
    def verified(method,path,**kwargs):
        calls.append((method,path))
        assert method=='GET' and path.startswith('/admin/users/')
        return identities[2]
    monkeypatch.setattr(team,'auth_request',verified)
    login(1)
    result=client.post('/api/v1/team/invitations',headers={'X-Organization-ID':'1'},json={'name':'Verified recipient','email':identities[2]['email'],'role':'viewer'})
    assert result.status_code==200 and result.json()['acceptance_available'],result.text
    invitation=result.json()['id']
    assert calls and all(method=='GET' for method,path in calls)
    login(2)
    assert any(row['id']==invitation for row in client.get('/api/v1/auth/invitations').json())
    assert client.post(f'/api/v1/auth/invitations/{invitation}/accept').status_code==200
    assert client.post('/api/v1/auth/organization',json={'organization_id':1}).status_code==200
    assert client.post('/api/v1/companies',json={'name':'Viewer blocked'}).status_code==403


def test_recovery_delivery_gate_never_calls_provider(control,monkeypatch):
    client,_,_,_=control
    monkeypatch.setattr(settings,'AUTH_EMAIL_CONFIGURATION_VERIFIED',False)
    from app.api.routes import auth
    monkeypatch.setattr(auth,'auth_request',lambda *a,**k:pytest.fail('Unavailable recovery must not send'))
    assert client.get('/api/v1/auth/config').json()['recovery_available'] is False
    assert client.post('/api/v1/auth/forgot-password',json={'email':'approved@example.com'}).status_code==503


def test_mfa_required_for_every_platform_operation_and_provider_sessions(control,monkeypatch):
    client,engine,login,ids=control
    import jwt
    from app.services import platform
    from app.core import sessions
    from app.api.routes import platform_auth
    monkeypatch.setattr(settings,'PLATFORM_MFA_REQUIRED',True)
    factor='00000000-0000-0000-0000-000000000099'
    identity={**ids[3],'factors':[{'id':factor,'status':'verified','factor_type':'totp'}]}
    def token(aal):return jwt.encode({'sub':ids[3]['id'],'aal':aal},key='',algorithm='none')
    with Session(engine) as db:
        row=db.scalar(sa.select(AuthSession).where(AuthSession.user_id==3));row.access_token=encrypt(token('aal1'));db.commit()
    def provider(method,path,data=None,**kwargs):
        if path=='/user':return identity
        if path.endswith('/challenge'):return {'id':str(uuid4())}
        if path.endswith('/verify'):return {'user':identity,'access_token':token('aal2'),'refresh_token':'refreshed-server-only','expires_in':3600}
        if path.startswith('/logout'):return {}
        raise AssertionError(path)
    for module in (platform,sessions,platform_auth):monkeypatch.setattr(module,'auth_request',provider)
    assert client.get('/api/v1/platform/summary').status_code==403
    assert client.get('/api/v1/auth/platform/mfa').json()['ready'] is False
    result=client.post('/api/v1/auth/platform/mfa/verify',json={'factor_id':factor,'code':'123456'})
    assert result.status_code==200,result.text
    assert 'access_token' not in result.text and 'refresh_token' not in result.text
    assert client.get('/api/v1/platform/summary').status_code==200
    assert client.post('/api/v1/auth/platform/sessions/revoke').status_code==200
    assert client.get('/api/v1/platform/summary').status_code==401
