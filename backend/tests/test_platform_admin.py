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
    assert client.get('/api/v1/platform/summary').json()=={'businesses':2,'active':2,'suspended':0,'memberships':3}
    assert len(client.get('/api/v1/platform/organizations?q=A&status=active').json())==1
    result=client.get('/api/v1/platform/organizations/1')
    assert result.status_code==200 and result.json()['verified_owners']==[]
    assert 'Tenant1Only' not in result.text and 'password' not in result.text
    for path in ('companies','contacts','deals','attachments/1/content','audit-logs/'):
        assert client.get('/api/v1/'+path,headers={'X-Organization-ID':'1'}).status_code==403

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
