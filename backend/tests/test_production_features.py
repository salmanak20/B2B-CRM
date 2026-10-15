from datetime import datetime,timedelta,timezone
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.models.session import AuthSession
from app.models.user import User
from app.models.company import Company
from app.models.task import Task
from app.models.notification import Notification
from app.models.workspace import WorkflowRun
from app.core.config import settings
from app.core.sessions import session_key
from tests.utils import auth_headers,create_user,create_company,create_contact,create_lead,create_pipeline,create_pipeline_stage

def test_cookie_login_restore_remember_expiry_and_logout(client,db):
    user=create_user(db,'sales_rep',password='SecureTestPassword!')
    r=client.post('/api/v1/auth/login?remember=true',data={'username':user.email,'password':'SecureTestPassword!'})
    assert r.status_code==200
    cookie=r.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie and 'Max-Age=2592000' in cookie
    assert client.get('/api/v1/auth/me').json()['id']==user.id
    raw=client.cookies.get(settings.SESSION_COOKIE_NAME)
    assert db.get(AuthSession,session_key(raw))
    assert client.post('/api/v1/auth/logout').status_code==204
    client.cookies.set(settings.SESSION_COOKIE_NAME,raw,path='/api')
    assert client.get('/api/v1/auth/me').status_code==401

def test_cookie_session_expiration(client,db):
    user=create_user(db,password='SecureTestPassword!')
    r=client.post('/api/v1/auth/login',data={'username':user.email,'password':'SecureTestPassword!'})
    assert 'Max-Age' not in r.headers['set-cookie']
    session=db.get(AuthSession,session_key(client.cookies.get(settings.SESSION_COOKIE_NAME)))
    session.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    assert client.get('/api/v1/auth/me').status_code==401

@pytest.mark.parametrize('password',['x','a'*100,'😀'*30])
def test_password_validation_is_controlled(client,password):
    r=client.post('/api/v1/auth/register',json={'name':'Password boundary','email':f'{uuid4().hex}@example.com','password':password})
    assert r.status_code==422

def test_auth_rate_limit_shared_database(client):
    responses=[client.post('/api/v1/auth/login',data={'username':'does-not-exist@example.com','password':'wrong'}) for _ in range(settings.LOGIN_RATE_LIMIT+1)]
    assert responses[-1].status_code==429
    assert 'Retry-After' in responses[-1].headers

def test_cross_origin_cookie_write_rejected(client,db):
    user=create_user(db,password='SecureTestPassword!')
    client.post('/api/v1/auth/login',data={'username':user.email,'password':'SecureTestPassword!'})
    r=client.post('/api/v1/companies',json={'name':'Blocked origin'},headers={'Origin':'https://attacker.example'})
    assert r.status_code==403

def test_administrator_changes_audited_and_self_deactivation_blocked(client,db):
    admin=create_user(db,'admin');other=create_user(db,'sales_rep')
    headers=auth_headers(client,admin.email)
    assert client.put('/api/v1/users/me',headers=headers,json={'name':'Changed profile'}).status_code==200
    assert client.put(f'/api/v1/users/{other.id}',headers=headers,json={'is_active':False}).status_code==200
    logs=client.get('/api/v1/audit-logs/',headers=headers).json()
    assert any(l['action']=='Profile Updated' and l['user_id']==admin.id for l in logs)
    assert any(l['action']=='User Updated' and l['entity_id']==other.id for l in logs)
    assert client.put(f'/api/v1/users/{admin.id}',headers=headers,json={'is_active':False}).status_code==409

def test_profile_preferences_validate_and_persist(client,db):
    user=create_user(db);headers=auth_headers(client,user.email)
    r=client.put('/api/v1/users/me',headers=headers,json={'preferences':{'timezone':'Asia/Karachi','compact_view':True}})
    assert r.status_code==200 and r.json()['preferences']['compact_view'] is True
    assert client.get('/api/v1/users/me',headers=headers).json()['preferences']['timezone']=='Asia/Karachi'
    assert client.put('/api/v1/users/me',headers=headers,json={'preferences':{'timezone':'not-a-zone'}}).status_code==422
    assert client.put('/api/v1/users/me',headers=headers,json={'preferences':{'role':'admin'}}).status_code==422

def test_csv_preview_commit_duplicate_and_partial_error_reporting(client,db):
    user=create_user(db);headers=auth_headers(client,user.email)
    name=f'CSV {uuid4().hex}'
    data={'csv_text':f'Company,Email\n{name},buyer@example.com\nInvalid,bad-address\n','mapping':{'name':'Company','email':'Email'},'mode':'skip'}
    before=db.query(Company).filter_by(owner_id=user.id).count()
    p=client.post('/api/v1/imports/companies/preview',headers=headers,json=data)
    assert p.status_code==200 and p.json()['valid']==1 and p.json()['invalid']==1
    assert db.query(Company).filter_by(owner_id=user.id).count()==before
    r=client.post('/api/v1/imports/companies/commit',headers=headers,json=data).json()
    assert r['created']==1 and r['failed']==1 and r['errors'][0]['row']==3
    r=client.post('/api/v1/imports/companies/commit',headers=headers,json=data).json()
    assert r['created']==0 and r['skipped']==1
    data['mode']='update';data['csv_text']=f'Company,Email\n{name},updated@example.com\n'
    assert client.post('/api/v1/imports/companies/commit',headers=headers,json=data).json()['updated']==1
    assert db.scalar(select(Company).where(Company.owner_id==user.id,Company.name==name)).email=='updated@example.com'

def test_import_cannot_set_ownership_or_link_inaccessible_company(client,db):
    a=create_user(db);b=create_user(db);ha=auth_headers(client,a.email);hb=auth_headers(client,b.email)
    company=create_company(client,hb)
    data={'csv_text':'Name,Company\nBuyer,'+str(company['id'])+'\n','mapping':{'first_name':'Name','company_id':'Company'}}
    preview=client.post('/api/v1/imports/contacts/preview',headers=ha,json=data).json()
    assert preview['invalid']==1
    data['mapping']['owner_id']='Company'
    assert client.post('/api/v1/imports/contacts/preview',headers=ha,json=data).status_code==422

def test_csv_formula_cells_are_neutralized(client,db):
    user=create_user(db,'admin');headers=auth_headers(client,user.email)
    company=create_company(client,headers,name='=SUM(1,2)')
    text=client.get('/api/v1/exports/companies',headers=headers).text
    assert "'=SUM(1,2)" in text

def test_lead_conversion_is_persistent_and_idempotent(client,db):
    user=create_user(db,'admin');headers=auth_headers(client,user.email)
    pipeline=create_pipeline(client,headers);stage=create_pipeline_stage(client,headers,pipeline['id'])
    lead=create_lead(client,headers)
    payload={'company_name':'Conversion '+uuid4().hex,'first_name':'Actual','last_name':'Buyer','email':uuid4().hex+'@example.com','pipeline_id':pipeline['id'],'stage_id':stage['id']}
    first=client.post(f"/api/v1/leads/{lead['id']}/convert",headers=headers,json=payload)
    assert first.status_code==200
    again=client.post(f"/api/v1/leads/{lead['id']}/convert",headers=headers,json=payload)
    assert again.json()['already_converted'] is True
    assert first.json()['deal_id']==again.json()['deal_id']
    record=client.get(f"/api/v1/leads/{lead['id']}",headers=headers).json()
    assert record['status']=='converted' and record['company']['name']==payload['company_name']

def test_workflow_runs_once_and_produces_assigned_task_notification(client,db):
    admin=create_user(db,'admin');rep=create_user(db);headers=auth_headers(client,admin.email)
    rule=client.post('/api/v1/workflows',headers=headers,json={'name':'Qualified follow-up','task_title':'Reach out to buyer','assigned_to_id':rep.id,'min_value':100}).json()
    lead=create_lead(client,headers,status='new',estimated_value=1000)
    for status in ['qualified','new','qualified']:
        assert client.put(f"/api/v1/leads/{lead['id']}",headers=headers,json={'status':status}).status_code==200
    assert db.query(WorkflowRun).filter_by(rule_id=rule['id'],lead_id=lead['id']).count()==1
    task=db.scalar(select(Task).where(Task.lead_id==lead['id']))
    assert task.assigned_to_id==rep.id
    assert db.scalar(select(Notification).where(Notification.user_id==rep.id,Notification.related_entity_id==task.id))

def test_assigned_tasks_search_and_due_notifications(client,db):
    admin=create_user(db,'admin');rep=create_user(db);headers=auth_headers(client,admin.email)
    task=client.post('/api/v1/tasks',headers=headers,json={'title':'Assigned '+uuid4().hex,'assigned_to_id':rep.id,'due_date':'2020-01-01T00:00:00Z'}).json()
    rep_headers=auth_headers(client,rep.email)
    results=client.get('/api/v1/search/',params={'q':task['title']},headers=rep_headers).json()
    assert any(t['id']==task['id'] for t in results['tasks'])
    assert client.post('/api/v1/notifications/check-due',headers=rep_headers).json()['created']==1
    assert client.post('/api/v1/notifications/check-due',headers=rep_headers).json()['created']==0

def test_whitespace_and_report_range_validation(client,db):
    user=create_user(db,'admin');headers=auth_headers(client,user.email)
    assert client.post('/api/v1/companies',headers=headers,json={'name':'   '}).status_code==422
    assert client.get('/api/v1/reports/sales?start_date=2026-10-20T00:00:00&end_date=2026-10-01T00:00:00',headers=headers).status_code==422

def test_company_delete_preserves_related_records(client,db):
    user=create_user(db,'admin');headers=auth_headers(client,user.email)
    company=create_company(client,headers);contact=create_contact(client,headers,company['id'])
    assert client.delete('/api/v1/companies/'+str(company['id']),headers=headers).status_code==409
    assert client.get('/api/v1/contacts/'+str(contact['id']),headers=headers).status_code==200

def test_sort_is_safe_and_pagination_reaches_all_records(client,db):
    user=create_user(db);headers=auth_headers(client,user.email)
    for name in ['Zeta','Alpha','Beta']:create_company(client,headers,name=name)
    r=client.get('/api/v1/companies?sort_by=name&page_size=2',headers=headers).json()
    assert [c['name'] for c in r['items']]==['Alpha','Beta'] and r['total']==3
    assert client.get('/api/v1/companies?sort_by=name&page_size=2&page=2',headers=headers).json()['items'][0]['name']=='Zeta'
    assert client.get('/api/v1/companies?sort_by=password_hash',headers=headers).status_code==422

def test_provider_login_uses_verified_identity_and_does_not_return_tokens(client,db,monkeypatch):
    import app.api.routes.auth as auth
    import app.core.sessions as sessions
    user=create_user(db);user.auth_user_id=str(uuid4());db.commit()
    identity={'id':user.auth_user_id,'email':user.email,'email_confirmed_at':'2026-10-15T00:00:00Z'}
    data={'access_token':'provider-access','refresh_token':'provider-refresh','expires_in':3600,'user':identity}
    monkeypatch.setattr(settings,'AUTH_PROVIDER','supabase')
    monkeypatch.setattr(auth,'auth_request',lambda *args,**kwargs:data)
    monkeypatch.setattr(sessions,'auth_request',lambda *args,**kwargs:identity)
    r=client.post('/api/v1/auth/login',data={'username':user.email,'password':'provided-to-provider'})
    assert r.status_code==200 and 'access_token' not in r.json()
    assert client.get('/api/v1/auth/me').json()['id']==user.id
    row=db.get(AuthSession,session_key(client.cookies.get(settings.SESSION_COOKIE_NAME)))
    assert 'provider-access' not in row.access_token and 'provider-refresh' not in row.refresh_token

def test_provider_recovery_verification_password_change_and_revocation(client,db,monkeypatch):
    import app.api.routes.auth as auth
    import app.core.sessions as sessions
    user=create_user(db);user.auth_user_id=str(uuid4());db.commit()
    identity={'id':user.auth_user_id,'email':user.email,'email_confirmed_at':'2026-10-15T00:00:00Z'}
    calls=[]
    def provider(method,path,data=None,**kwargs):
        calls.append((method,path,data))
        if path=='/verify':return {'access_token':'recovery-access','refresh_token':'refresh','expires_in':3600,'user':identity}
        return identity
    monkeypatch.setattr(settings,'AUTH_PROVIDER','supabase')
    monkeypatch.setattr(auth,'auth_request',provider)
    monkeypatch.setattr(sessions,'auth_request',provider)
    assert client.post('/api/v1/auth/forgot-password',json={'email':user.email}).status_code==200
    assert client.post('/api/v1/auth/recovery/verify',json={'token_hash':'provider-validated-token','type':'recovery'}).status_code==200
    assert client.post('/api/v1/auth/password',json={'password':'NewSecurePassword!'}).status_code==200
    assert client.get('/api/v1/auth/me').status_code==401
    assert any(method=='PUT' and path=='/user' for method,path,_ in calls)
    assert any(path=='/logout?scope=global' for _,path,_ in calls)
