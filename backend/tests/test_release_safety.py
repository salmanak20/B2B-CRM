from datetime import datetime,timezone
from decimal import Decimal
from app.core.config import settings
from app.models.deal import Deal
from uuid import uuid4
from tests.utils import auth_headers,create_user,create_company,create_pipeline,create_pipeline_stage,create_deal


def test_private_attachment_permissions_validation_and_parent_integrity(client,db,monkeypatch):
    import app.api.routes.attachments as attachments
    owner=create_user(db,'admin');other=create_user(db);viewer=create_user(db,'viewer')
    headers=auth_headers(client,owner.email);company=create_company(client,headers)
    monkeypatch.setattr(settings,'SUPABASE_URL','https://example.supabase.co')
    monkeypatch.setattr(settings,'SUPABASE_SERVICE_ROLE_KEY','server-only-contract-test')
    calls=[]
    def storage(method,path,**kwargs):
        calls.append((method,path,kwargs));return {'signedURL':'/object/sign/private/file?token=short-lived'} if '/sign/' in path else {}
    monkeypatch.setattr(attachments,'storage',storage)
    route=f"/api/v1/records/companies/{company['id']}/attachments"
    assert client.post(route,headers=headers,files={'file':('bad.pdf',b'not a pdf','application/pdf')}).status_code==422
    assert client.post(route,headers=headers,files={'file':('large.txt',b'x'*(3*1024*1024+1),'text/plain')}).status_code==413
    upload=client.post(route,headers=headers,files={'file':('contract.txt',b'Private customer document','text/plain')})
    assert upload.status_code==200
    record=upload.json();assert record['size']==25
    assert 'service_role' not in upload.text
    assert client.delete(f"/api/v1/companies/{company['id']}",headers=headers).status_code==409
    other_headers=auth_headers(client,other.email)
    assert client.get(f"/api/v1/attachments/{record['id']}/download",headers=other_headers).status_code==403
    view_headers=auth_headers(client,viewer.email)
    assert client.delete(f"/api/v1/attachments/{record['id']}",headers=view_headers).status_code==403
    assert client.get(f"/api/v1/attachments/{record['id']}/download",headers=headers).status_code==200
    assert calls[-1][2]['json']['expiresIn']==60
    assert client.delete(f"/api/v1/attachments/{record['id']}",headers=headers).status_code==200
    assert client.delete(f"/api/v1/companies/{company['id']}",headers=headers).status_code==200


def test_revenue_uses_actual_close_date_and_preserves_unknown_history(client,db):
    user=create_user(db,'sales_manager');headers=auth_headers(client,user.email)
    pipeline=create_pipeline(client,headers);open_stage=create_pipeline_stage(client,headers,pipeline['id'])
    won_stage=create_pipeline_stage(client,headers,pipeline['id'],order=2,is_closed=True,is_won=True,probability=100)
    deal=create_deal(client,headers,pipeline['id'],open_stage['id'],value=1234.56)
    closed=client.patch(f"/api/v1/deals/{deal['id']}/stage",headers=headers,json={'stage_id':won_stage['id']}).json()
    assert closed['closed_at']
    assert client.put(f"/api/v1/deals/{deal['id']}",headers=headers,json={'title':'Updated after closing'}).json()['closed_at']==closed['closed_at']
    row=db.get(Deal,deal['id']);row.created_at=datetime(2030,1,1,tzinfo=timezone.utc);row.closed_at=datetime(2031,2,1,tzinfo=timezone.utc);db.commit()
    for route in ['summary','sales-performance','pipeline-analytics']:
        result=client.get('/api/v1/dashboard/'+route+'?start_date=2031-02-01&end_date=2031-02-28',headers=headers)
        assert result.status_code==200 and Decimal(result.json()['won_revenue'])==Decimal('1234.56')
    team=client.get('/api/v1/dashboard/team-performance?start_date=2031-02-01&end_date=2031-02-28',headers=headers).json()
    assert Decimal(next(row for row in team['users'] if row['user_id']==user.id)['won_revenue'])==Decimal('1234.56')
    row.closed_at=None;db.commit()
    trend=client.get('/api/v1/dashboard/revenue-trend',headers=headers).json()
    assert any(d['period']=='Unknown close date' for d in trend['data'])
    assert Decimal(client.get('/api/v1/dashboard/summary?start_date=2031-02-01&end_date=2031-02-28',headers=headers).json()['won_revenue'])==0
    reopened=client.patch(f"/api/v1/deals/{deal['id']}/stage",headers=headers,json={'stage_id':open_stage['id']}).json()
    assert reopened['closed_at'] is None


def test_due_reminders_are_delivered_on_fetch_once(client,db):
    user=create_user(db);headers=auth_headers(client,user.email)
    task=client.post('/api/v1/tasks',headers=headers,json={'title':'Due for this user','assigned_to_id':user.id,'due_date':'2020-01-01T00:00:00Z'}).json()
    first=client.get('/api/v1/notifications/',headers=headers).json()
    second=client.get('/api/v1/notifications/',headers=headers).json()
    assert len([r for r in first if r['notification_type']=='task_due' and r['related_entity_id']==task['id']])==1
    assert len(first)==len(second)


def test_existing_identity_migration_preserves_profile_owner_and_role(client,db,monkeypatch):
    import app.api.routes.auth as auth
    import app.api.routes.users as users
    import app.core.sessions as sessions
    admin=create_user(db,'admin');account=create_user(db)
    admin.auth_user_id=str(uuid4());db.commit()
    headers=auth_headers(client,account.email);company=create_company(client,headers)
    original_role=account.role_id;original_id=account.id
    identity={'id':admin.auth_user_id,'email':admin.email,'email_confirmed_at':'2026-10-15T00:00:00Z'}
    monkeypatch.setattr(settings,'AUTH_PROVIDER','supabase')
    monkeypatch.setattr(auth,'auth_request',lambda *a,**kw:{'access_token':'admin-access','refresh_token':'admin-refresh','expires_in':3600,'user':identity})
    monkeypatch.setattr(sessions,'auth_request',lambda *a,**kw:identity)
    assert client.post('/api/v1/auth/login',data={'username':admin.email,'password':'provider-validated'}).status_code==200
    target_id=str(uuid4())
    monkeypatch.setattr(users,'auth_request',lambda *a,**kw:{'id':target_id,'email':'wrong@example.com','email_confirmed_at':'2026-10-15T00:00:00Z'})
    route=f'/api/v1/users/{original_id}/invite'
    assert client.post(route,json={'auth_user_id':target_id}).status_code==422
    monkeypatch.setattr(users,'auth_request',lambda *a,**kw:{'id':target_id,'email':account.email,'email_confirmed_at':'2026-10-15T00:00:00Z'})
    result=client.post(route,json={'auth_user_id':target_id})
    assert result.status_code==200 and result.json()['auth_linked'] is True
    assert result.json()['id']==original_id and result.json()['role']['id']==original_role
    from app.models.company import Company
    assert db.get(Company,company['id']).owner_id==original_id
    assert client.post(route,json={'auth_user_id':target_id}).status_code==409
