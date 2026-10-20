import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from fastapi import HTTPException
from tests.test_business_onboarding import business,api,isolation_engine
from app.models import User,Organization,Membership,Company
from app.models.platform import PlatformAdministrator,PlatformAudit
from app.services import platform
from app.db.tenant_session import TenantSession

@pytest.fixture
def control(business,monkeypatch):
    client,engine,login,identities,calls=business
    original=platform.auth_request
    def provider(method,path,**kwargs):
        if path.startswith('/admin/users/'):
            return next(dict(i) for i in identities.values() if i['id']==path.split('/')[-1])
        if path=='/user':return dict(identities[int(kwargs['token'].split('-')[-1])])
        return original(method,path,**kwargs)
    monkeypatch.setattr(platform,'auth_request',provider)
    with Session(engine) as db:platform.bootstrap(db,3,identities[3]['email'],identities[3]['id'])
    login(3)
    return client,engine,login,identities

def test_bootstrap_explicit_verified_closed_and_no_role_changes(control):
    client,engine,_,ids=control
    with Session(engine) as db:
        assert db.get(User,3).role.name=='admin'
        assert db.scalar(sa.select(Membership).where(Membership.user_id==3)) is None
        assert db.scalar(sa.select(PlatformAudit.action))=='administrator_bootstrap'
        with pytest.raises(HTTPException):platform.bootstrap(db,1,ids[1]['email'],ids[1]['id'])
    assert client.get('/api/v1/auth/platform-access').json()=={'is_platform_admin':True}

@pytest.mark.parametrize('uid',[1,2])
def test_business_roles_cannot_self_promote(control,uid):
    client,engine,login,_=control
    with Session(engine) as db:
        if uid==1:db.scalar(sa.select(Membership).where(Membership.user_id==1,Membership.organization_id==1)).role='owner';db.commit()
    login(uid)
    for path in ('summary','organizations','administrators','activity'):
        assert client.get('/api/v1/platform/'+path).status_code==403
    assert client.put(f'/api/v1/platform/administrators/{uid}',json={'is_active':True,'reason':'Forbidden'}).status_code==403

def test_real_metrics_search_details_and_no_crm_access(control):
    client,engine,_,_=control
    metrics=client.get('/api/v1/platform/summary').json()
    assert metrics==dict(businesses=2,active=0,suspended=0,expired=0,pending=2,memberships=3,occupied_seats=3,active_users=2,active_pilots=0,expiring_pilots=0)
    assert len(client.get('/api/v1/platform/organizations?q=A&status=pending').json())==1
    result=client.get('/api/v1/platform/organizations/1')
    assert result.status_code==200 and result.json()['verified_owners']==[]
    assert 'Tenant1Only' not in result.text and 'password' not in result.text
    for path in ('companies','contacts','deals','attachments/1/content','audit-logs/'):
        assert client.get('/api/v1/'+path,headers={'X-Organization-ID':'1'}).status_code==403
    with Session(engine) as db:db.get(User,2).is_active=False;db.commit()
    metrics=client.get('/api/v1/platform/summary').json()
    assert metrics['active_users']==1 and metrics['occupied_seats']==3

def test_suspend_reactivate_preserves_data_and_blocks_sessions_and_workers(control):
    client,engine,login,_=control
    with Session(engine) as db:before=[tuple(r) for r in db.execute(sa.select(Company.__table__))]
    assert client.put('/api/v1/platform/organizations/1',json={'is_suspended':True,'reason':'Review'}).status_code==200
    assert client.get('/api/v1/platform/summary').json()['suspended']==1
    login(1)
    assert client.post('/api/v1/auth/organization',json={'organization_id':1}).status_code==403
    assert all(o['id']!=1 for o in client.get('/api/v1/auth/organizations').json())
    for method,path,body in [('get','companies',None),('post','companies',{'name':'Blocked'}),('get','dashboard/summary',None),('get','attachments/1/content',None)]:
        assert client.request(method,'/api/v1/'+path,headers={'X-Organization-ID':'1'},json=body).status_code==403
    from app.services.reminders import deliver_due
    with TenantSession(engine) as db:
        db.info['organization_id']=1
        with pytest.raises(HTTPException):deliver_due(db)
    login(3)
    assert client.put('/api/v1/platform/organizations/1',json={'is_suspended':False,'reason':'Resolved'}).status_code==200
    login(1)
    assert client.post('/api/v1/auth/organization',json={'organization_id':1}).status_code==200
    assert client.get('/api/v1/companies').status_code==200
    with Session(engine) as db:
        assert [tuple(r) for r in db.execute(sa.select(Company.__table__))]==before
        assert db.scalar(sa.select(sa.func.count()).select_from(PlatformAudit))==3

def test_grant_revoke_final_admin_and_immediate_access_loss(control):
    client,engine,login,_=control
    assert client.put('/api/v1/platform/administrators/3',json={'is_active':False,'reason':'No'}).status_code==409
    assert client.put('/api/v1/platform/administrators/2',json={'is_active':True,'reason':'Approved verified operator'}).status_code==200
    assert len(client.get('/api/v1/platform/administrators').json())==2
    assert client.put('/api/v1/platform/administrators/3',json={'is_active':False,'reason':'Handover'}).status_code==200
    assert client.get('/api/v1/platform/summary').status_code==403
    login(2)
    assert client.get('/api/v1/platform/summary').status_code==200
    assert client.put('/api/v1/platform/administrators/2',json={'is_active':False,'reason':'Final'}).status_code==409

@pytest.mark.parametrize('failure',['unverified','inactive','unlinked'])
def test_invalid_grant_fails_without_audit_or_permissions(control,failure):
    client,engine,_,ids=control
    if failure=='unverified':ids[2]['email_confirmed_at']=None
    else:
        with Session(engine) as db:
            if failure=='inactive':db.get(User,2).is_active=False
            else:db.get(User,2).auth_user_id=None
            db.commit()
    assert client.put('/api/v1/platform/administrators/2',json={'is_active':True,'reason':'Denied'}).status_code==422
    with Session(engine) as db:
        assert db.get(PlatformAdministrator,2) is None
        assert db.scalar(sa.select(sa.func.count()).select_from(PlatformAudit))==1

def test_verified_owner_details_and_no_unverified_claims(control):
    client,engine,_,ids=control
    with Session(engine) as db:db.scalar(sa.select(Membership).where(Membership.user_id==1,Membership.organization_id==1)).role='owner';db.commit()
    assert client.get('/api/v1/platform/organizations/1').json()['verified_owners'][0]['id']==1
    ids[1]['email_confirmed_at']=None
    assert client.get('/api/v1/platform/organizations/1').json()['verified_owners']==[]

def test_recovery_session_and_changed_auth_link_denied(control):
    client,engine,_,ids=control
    from app.models.session import AuthSession
    with Session(engine) as db:
        db.scalar(sa.select(AuthSession).where(AuthSession.user_id==3)).recovery=True;db.commit()
    assert client.get('/api/v1/platform/summary').status_code==403

def test_audit_failure_rolls_back_suspension(control,monkeypatch):
    client,engine,_,_=control
    from app.api.routes import platform as routes
    def fail(*args):raise HTTPException(503,'Audit unavailable')
    monkeypatch.setattr(routes,'audit',fail)
    assert client.put('/api/v1/platform/organizations/1',json={'is_suspended':True,'reason':'Rollback'}).status_code==503
    with Session(engine) as db:assert db.get(Organization,1).is_suspended is False

def test_bootstrap_refuses_implicit_or_unverified_identity(business,monkeypatch):
    _,engine,_,ids,_=business
    monkeypatch.setattr(platform,'auth_request',lambda *a,**k:ids[3])
    with Session(engine) as db:
        with pytest.raises(HTTPException):platform.bootstrap(db,3,'wrong@example.com',ids[3]['id'])
        assert db.scalar(sa.select(sa.func.count()).select_from(PlatformAdministrator))==0
        ids[3]['email_confirmed_at']=None
        with pytest.raises(HTTPException):platform.bootstrap(db,3,ids[3]['email'],ids[3]['id'])
        assert db.scalar(sa.select(sa.func.count()).select_from(PlatformAudit))==0

def test_auth_binding_and_unverified_session_lose_platform_access(control):
    client,engine,_,ids=control
    ids[3]['email_confirmed_at']=None
    assert client.get('/api/v1/platform/summary').status_code==403
    ids[3]['email_confirmed_at']='2026-10-17T00:00:00Z'
    with Session(engine) as db:db.get(PlatformAdministrator,3).auth_user_id=ids[2]['id'];db.commit()
    assert client.get('/api/v1/platform/summary').status_code==403


@pytest.mark.parametrize('uid',[1,2])
def test_new_metadata_and_revocation_endpoints_deny_business_users(control,uid):
    client,engine,login,_=control
    if uid==1:
        with Session(engine) as db:
            db.scalar(sa.select(Membership).where(Membership.organization_id==1,Membership.user_id==uid)).role='owner';db.commit()
    login(uid)
    for path in ('members','invitations','members/1/identity'):
        assert client.get('/api/v1/platform/organizations/1/'+path).status_code==403
    for path in ('members/1/revoke','invitations/1/revoke'):
        assert client.put('/api/v1/platform/organizations/1/'+path,json={'reason':'Forbidden'}).status_code==403


def test_member_metadata_verification_and_cross_org_lookup(control):
    client,engine,_,ids=control
    result=client.get('/api/v1/platform/organizations/1/members')
    assert [m['user_id'] for m in result.json()]==[1]
    assert result.json()[0]['auth_linked'] is True
    assert not any(k in result.text for k in ('password','access_token','Tenant1Only','auth_user_id'))
    assert client.get('/api/v1/platform/organizations/1/members/2/identity').status_code==404
    assert client.get('/api/v1/platform/organizations/1/members/1/identity').json()=={'verified':True}
    ids[1]['email_confirmed_at']=None
    assert client.get('/api/v1/platform/organizations/1/members/1/identity').json()['verified'] is False
    assert client.get('/api/v1/platform/organizations/999/members').status_code==404


def test_membership_revocation_preserves_other_org_and_global_identity(control):
    client,engine,login,_=control
    from app.models.session import AuthSession
    login(1)
    assert client.post('/api/v1/auth/organization',json={'organization_id':1}).status_code==200
    raw=client.cookies.get('crm_session')
    login(3)
    with Session(engine) as db:
        before=[tuple(r) for r in db.execute(sa.select(Company.__table__))]
    assert client.put('/api/v1/platform/organizations/1/members/2/revoke',json={'reason':'Wrong business'}).status_code==404
    assert client.put('/api/v1/platform/organizations/1/members/1/revoke',json={'reason':'Approved access review'}).status_code==200
    with Session(engine) as db:
        assert db.get(User,1).is_active
        assert not db.scalar(sa.select(Membership).where(Membership.organization_id==1,Membership.user_id==1)).is_active
        assert db.scalar(sa.select(Membership).where(Membership.organization_id==2,Membership.user_id==1)).is_active
        assert db.scalar(sa.select(AuthSession).where(AuthSession.user_id==1,AuthSession.active_organization_id==1)) is None
        assert [tuple(r) for r in db.execute(sa.select(Company.__table__))]==before
        assert db.scalar(sa.select(PlatformAudit).where(PlatformAudit.action=='membership_revoked')).target_id==1
    client.cookies.set('crm_session',raw)
    assert client.get('/api/v1/companies',headers={'X-Organization-ID':'1'}).status_code==401
    client.cookies.clear();login(1)
    assert client.get('/api/v1/companies',headers={'X-Organization-ID':'1'}).status_code==403
    assert client.get('/api/v1/companies',headers={'X-Organization-ID':'2'}).status_code==200


def test_final_owner_and_audit_failure_prevent_revocation(control,monkeypatch):
    client,engine,_,_=control
    from app.api.routes import platform as routes
    with Session(engine) as db:
        db.scalar(sa.select(Membership).where(Membership.organization_id==1,Membership.user_id==1)).role='owner';db.commit()
    path='/api/v1/platform/organizations/1/members/1/revoke'
    assert client.put(path,json={'reason':'Cannot orphan business'}).status_code==409
    with Session(engine) as db:
        db.scalar(sa.select(Membership).where(Membership.organization_id==1,Membership.user_id==1)).role='admin';db.commit()
    def fail(*args):raise HTTPException(503,'Audit unavailable')
    monkeypatch.setattr(routes,'audit',fail)
    assert client.put(path,json={'reason':'Atomic audit test'}).status_code==503
    with Session(engine) as db:
        assert db.scalar(sa.select(Membership).where(Membership.organization_id==1,Membership.user_id==1)).is_active


def test_pending_invitation_metadata_scoped_revoke_no_provider_email(control):
    client,engine,_,ids=control
    from app.models.invitation import OrganizationInvitation
    from app.core.sessions import utcnow
    from datetime import timedelta
    with Session(engine) as db:
        for org in (1,2):
            db.add(OrganizationInvitation(organization_id=org,email=f'pending{org}@example.com',name='Pending',role='viewer',invited_by=org,provider_user_id=ids[org]['id'],expires_at=utcnow()+timedelta(days=1)))
        db.commit()
    pending=client.get('/api/v1/platform/organizations/1/invitations').json()
    assert len(pending)==1 and pending[0]['email']=='pending1@example.com'
    other=client.get('/api/v1/platform/organizations/2/invitations').json()[0]['id']
    assert client.put(f'/api/v1/platform/organizations/1/invitations/{other}/revoke',json={'reason':'Wrong organization'}).status_code==404
    assert client.put(f"/api/v1/platform/organizations/1/invitations/{pending[0]['id']}/revoke",json={'reason':'Approved cancellation'}).status_code==200
    assert client.get('/api/v1/platform/organizations/1/invitations').json()==[]
    assert len(client.get('/api/v1/platform/organizations/2/invitations').json())==1
    with Session(engine) as db:assert db.scalar(sa.select(PlatformAudit.action).where(PlatformAudit.action=='invitation_revoked'))=='invitation_revoked'


def test_pilot_metrics_and_filters_use_dates_and_suspension(control):
    client,engine,_,_=control
    from app.models.subscription import Subscription,SubscriptionPlan
    from app.services.subscriptions import pilot_definition
    from app.core.sessions import utcnow
    from datetime import timedelta
    with Session(engine) as db:
        plan=SubscriptionPlan(code='free_pilot',**pilot_definition());db.add(plan);db.flush()
        for org,days in [(1,3),(2,-1)]:
            db.add(Subscription(organization_id=org,plan_id=plan.id,status='active',starts_at=utcnow()-timedelta(days=29),ends_at=utcnow()+timedelta(days=days),enforcement_enabled=True))
        db.commit()
    metrics=client.get('/api/v1/platform/summary').json()
    assert (metrics['active'],metrics['expired'],metrics['active_pilots'],metrics['expiring_pilots'])==(1,1,1,1)
    assert [o['id'] for o in client.get('/api/v1/platform/organizations?status=expired').json()]==[2]
    assert client.put('/api/v1/platform/organizations/1',json={'is_suspended':True,'reason':'Review'}).status_code==200
    metrics=client.get('/api/v1/platform/summary').json()
    assert (metrics['suspended'],metrics['active_pilots'],metrics['expiring_pilots'])==(1,0,0)
