"""Exercise existing routes and session guards against two isolated PG tenants."""
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, aliased

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import Base, get_db
from app.db.tenant_session import TenantSession
from app.db.tenant_backfill import staging_engine
from app.models import User, Role, Company, Contact, Lead, Deal, Pipeline, PipelineStage, Task, Activity, Membership, Organization
from app.models.workspace import WorkspaceSettings, WorkflowRule, Attachment
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.session import AuthSession
from app.db.seed import seed_db

FIXTURE_PASSWORD_HASH = hash_password("fixture-password")


@pytest.fixture(scope="module")
def isolation_engine():
    url=os.environ.get("CRM_TEST_MIGRATION_URL")
    if not url:
        pytest.skip("Run scripts/tenant_foundation_qa.py --isolation")
    engine=staging_engine(url)
    assert engine.url.database.startswith("crm_test_") and os.environ.get("CRM_TEST_RUN")=="1"
    with engine.connect() as db:
        assert sa.inspect(db).get_table_names()==[]
    command.upgrade(Config(str(Path(__file__).resolve().parents[1]/"alembic.ini")),"head")
    yield engine
    engine.dispose()


@pytest.fixture
def api(isolation_engine,monkeypatch):
    monkeypatch.setattr(settings,"TENANT_ISOLATION_ENABLED",True)
    assert isolation_engine.url.database.startswith("crm_test_")
    with isolation_engine.begin() as connection:
        names=",".join('"'+n+'"' for n in sa.inspect(connection).get_table_names() if n!="alembic_version")
        connection.execute(sa.text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    with Session(isolation_engine) as db:
        seed_db(db)
        roles={r.name:r for r in db.scalars(sa.select(Role))}
        db.add_all([Organization(id=1,name="A",slug="a"),Organization(id=2,name="B",slug="b")]);db.flush()
        # User 1 has a global admin role but is a viewer in B. User 3 has no membership.
        for uid in (1,2,3):
            db.add(User(id=uid,name=f"User {uid}",email=f"user{uid}@example.com",password_hash=FIXTURE_PASSWORD_HASH,role_id=roles["admin"].id,is_active=True))
        db.flush()
        db.add_all([Membership(organization_id=1,user_id=1,role="admin"),Membership(organization_id=2,user_id=1,role="viewer"),Membership(organization_id=2,user_id=2,role="admin")]);db.flush()
        for org,uid in ((1,1),(2,2)):
            tag=f"Tenant{org}Only"
            db.add(Company(id=org,organization_id=org,name=tag,owner_id=uid));db.flush()
            db.add(Contact(id=org,organization_id=org,name=tag,first_name=tag,company_id=org,owner_id=uid));db.flush()
            db.add(Lead(id=org,organization_id=org,name=tag,title=tag,status="qualified",owner_id=uid,company_id=org,contact_id=org));db.flush()
            db.add(Pipeline(id=org,organization_id=org,name=tag,is_default=True));db.flush()
            db.add(PipelineStage(id=org,organization_id=org,pipeline_id=org,name=tag,order=1,probability=25));db.flush()
            db.add(Deal(id=org,organization_id=org,title=tag,owner_id=uid,pipeline_id=org,stage_id=org,company_id=org,contact_id=org,lead_id=org,value=100*org,status="open"));db.flush()
            db.add(Task(id=org,organization_id=org,title=tag,owner_id=uid,assigned_to_id=uid,company_id=org,lead_id=org,deal_id=org,due_date=datetime.now(timezone.utc)-timedelta(days=1)));db.flush()
            db.add(Activity(id=org,organization_id=org,subject=tag,type="note",user_id=uid,company_id=org));db.flush()
            db.add_all([WorkspaceSettings(id=org,organization_id=org,name=tag,timezone="UTC",currency="USD"),
                WorkflowRule(id=org,organization_id=org,name=tag,owner_id=uid,task_title=tag),
                Attachment(id=org,organization_id=org,entity="companies",entity_id=org,uploaded_by=uid,name=tag,storage_path=f"original/{org}/file.txt",content_type="text/plain",size=10),
                Notification(id=org,organization_id=org,user_id=uid,title=tag,message=tag,notification_type="test"),
                AuditLog(id=org,organization_id=org,user_id=uid,action=tag,entity="User",entity_id=uid)])
        db.commit()
        # Explicit IDs above must not collide with subsequent legitimate API inserts.
        for table in Base.metadata.tables.values():
            if "id" in table.c and isinstance(table.c.id.type,sa.Integer):
                db.execute(sa.text(f"SELECT setval(pg_get_serial_sequence('{table.name}','id'),COALESCE((SELECT MAX(id) FROM {table.name}),1),(SELECT count(*)>0 FROM {table.name}))"))
        db.commit()
    def dependency():
        with TenantSession(isolation_engine,autoflush=False) as db:
            yield db
    app.dependency_overrides[get_db]=dependency
    with TestClient(app) as client:
        yield client,isolation_engine
    app.dependency_overrides.pop(get_db,None)


def headers(user=1,org=1):
    result={"Authorization":"Bearer "+create_access_token(user)}
    if org is not None: result["X-Organization-ID"]=str(org)
    return result


@pytest.mark.parametrize("path",["companies","contacts","leads","deals","pipelines","tasks","activities","workflows","directory","users","audit-logs/","search/?q=Tenant","exports/companies","exports/contacts","exports/leads","exports/deals","exports/tasks","reports/leads","reports/deals","reports/tasks","reports/team","dashboard/summary","dashboard/sales-performance","dashboard/lead-analytics","dashboard/pipeline-analytics","dashboard/revenue-trend","dashboard/activity-summary","dashboard/team-performance"])
def test_lists_search_exports_and_aggregates_are_scoped(api,path):
    client,_=api
    response=client.get("/api/v1/"+path,headers=headers())
    assert response.status_code==200,response.text
    assert "Tenant2Only" not in response.text
    if path=="dashboard/summary":
        assert response.json()["total_deals"]==response.json()["total_companies"]==1
        assert float(response.json()["total_pipeline_value"])==100
    if path=="reports/sales":
        assert response.json()["total_deals"]==1 and response.json()["total_value"]==100


@pytest.mark.parametrize("path",["companies/2","contacts/2","leads/2","deals/2","pipelines/2","pipeline-stages/2","pipelines/2/stages","tasks/2","activities/2","attachments/2/download","attachments/2/content","records/companies/2/attachments","records/companies/2/related","users/2","notifications/2"])
def test_cross_tenant_reads_are_hidden(api,path):
    client,_=api
    response=client.get("/api/v1/"+path,headers=headers())
    assert response.status_code==404,response.text


@pytest.mark.parametrize("method,path,body",[("put","companies/2",{"name":"stolen"}),("delete","companies/2",None),("delete","attachments/2",None),("patch","notifications/2/read",None),("delete","workflows/2",None)])
def test_cross_tenant_writes_are_hidden(api,method,path,body):
    client,engine=api
    response=client.request(method,"/api/v1/"+path,headers=headers(),json=body)
    assert response.status_code==404,response.text
    with Session(engine) as db:
        assert db.get(Company,2).name=="Tenant2Only"


def test_related_records_and_owners_cannot_cross_tenants(api):
    client,_=api
    for path,body in [("contacts",{"first_name":"Cross","company_id":2}),("companies",{"name":"Cross","owner_id":2}),
                      ("deals",{"title":"Cross","value":50,"pipeline_id":2,"stage_id":2})]:
        response=client.post("/api/v1/"+path,headers=headers(),json=body)
        assert response.status_code in {400,422},response.text


def test_missing_spoofed_revoked_context_and_org_roles(api):
    client,engine=api
    assert client.get("/api/v1/companies",headers=headers(org=None)).status_code==403 # Two choices, no selection.
    assert client.get("/api/v1/companies",headers=headers(org=999)).status_code==403
    assert client.get("/api/v1/companies",headers=headers(user=3)).status_code==403
    assert client.post("/api/v1/companies",headers=headers(org=2),json={"name":"Blocked viewer"}).status_code==403
    assert client.get("/api/v1/users",headers=headers(org=2)).status_code==403
    with Session(engine) as db:
        db.scalar(sa.select(Membership).where(Membership.user_id==1,Membership.organization_id==1)).is_active=False;db.commit()
    assert client.get("/api/v1/companies",headers=headers()).status_code==403
    assert client.get("/api/v1/companies",headers=headers(org=2)).status_code==200
    response=client.get("/api/v1/companies",headers=headers(org=2))
    assert "Tenant2Only" in response.text and "Tenant1Only" not in response.text


def test_legitimate_writes_scoped_settings_and_notifications(api):
    client,engine=api
    response=client.post("/api/v1/companies",headers=headers(),json={"name":"Legitimate"})
    assert response.status_code==200,response.text
    assert client.put("/api/v1/workspace",headers=headers(),json={"name":"Workspace A","timezone":"UTC","currency":"USD"}).status_code==200
    assert client.get("/api/v1/notifications/",headers=headers()).status_code==200
    assert client.patch("/api/v1/notifications/read-all",headers=headers()).status_code==200
    with Session(engine) as db:
        assert db.scalar(sa.select(Company).where(Company.name=="Legitimate")).organization_id==1
        assert db.get(WorkspaceSettings,2).name=="Tenant2Only"
        assert db.get(Notification,2).is_read is False
        assert {n.organization_id for n in db.scalars(sa.select(Notification).where(Notification.user_id==1))}=={1}


def test_cookie_organization_selection_is_validated_and_persisted(api):
    client,engine=api
    response=client.post("/api/v1/auth/login",data={"username":"user1@example.com","password":"fixture-password"})
    assert response.status_code==200,response.text
    assert client.get("/api/v1/companies").status_code==403
    assert client.post("/api/v1/auth/organization",json={"organization_id":999}).status_code==403
    assert client.post("/api/v1/auth/organization",json={"organization_id":1}).status_code==200
    assert "Tenant2Only" not in client.get("/api/v1/companies").text
    assert client.post("/api/v1/auth/organization",json={"organization_id":2}).status_code==200
    assert client.post("/api/v1/companies",json={"name":"Viewer blocked"}).status_code==403
    with Session(engine) as db:
        assert db.scalar(sa.select(AuthSession)).active_organization_id==2


def test_session_guard_covers_identity_map_aliases_bulk_and_missing_context(api):
    _,engine=api
    with TenantSession(engine) as db:
        with pytest.raises(HTTPException): db.scalars(sa.select(Company)).all()
        db.info["organization_id"]=1
        other=aliased(Company)
        assert [r.id for r in db.scalars(sa.select(other))]==[1]
        assert db.scalar(sa.select(sa.func.count()).select_from(sa.select(Company).subquery()))==1
        assert db.get(Company,2) is None
        assert db.execute(sa.delete(Company).where(Company.id==2)).rowcount==0
        with pytest.raises(HTTPException): db.execute(sa.text("SELECT * FROM companies"))
        with pytest.raises(HTTPException): db.execute(sa.update(Company).values(organization_id=2))
        db.rollback()


def test_background_delivery_has_explicit_tenant_scope(api):
    _,engine=api
    from app.services.reminders import deliver_due
    with TenantSession(engine) as db:
        with pytest.raises(HTTPException): deliver_due(db)
        db.info["organization_id"]=1
        assert deliver_due(db)==1
    with Session(engine) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(Notification).where(Notification.organization_id==2))==1


@pytest.mark.parametrize("role,create_status,delete_status",[("admin",200,200),("sales_manager",200,200),("sales_rep",200,403),("viewer",403,403)])
def test_existing_permissions_come_from_membership_not_global_role(api,role,create_status,delete_status):
    client,engine=api
    with Session(engine) as db:
        member=db.scalar(sa.select(Membership).where(Membership.organization_id==1,Membership.user_id==1))
        member.role=member.permission_role_name=role
        db.commit()
    assert client.post("/api/v1/companies",headers=headers(),json={"name":"Role test"}).status_code==create_status
    # A new empty record can be deleted without attachment/relationship conflicts.
    with Session(engine) as db:
        record=Company(name="Delete candidate",owner_id=1,organization_id=1)
        db.add(record);db.commit();record_id=record.id
    assert client.delete(f"/api/v1/companies/{record_id}",headers=headers()).status_code==delete_status
    with Session(engine) as db:
        assert db.get(User,1).role.name=="admin"
        assert (db.get(Company,record_id) is None)==(delete_status==200)


def test_shared_account_admin_changes_affect_only_current_membership(api):
    client,engine=api
    assert client.patch("/api/v1/users/1/status?is_active=false",headers=headers(user=2,org=2)).status_code==200
    assert client.get("/api/v1/companies",headers=headers(org=2)).status_code==403
    assert client.get("/api/v1/companies",headers=headers()).status_code==200
    with Session(engine) as db:
        assert db.get(User,1).is_active and db.get(User,1).role.name=="admin"


def test_legacy_null_rows_and_client_tenant_fields_are_not_trusted(api):
    client,engine=api
    with Session(engine) as db:
        row=Company(name="Unmapped legacy",owner_id=1)
        db.add(row);db.commit();record_id=row.id
    assert client.get(f"/api/v1/companies/{record_id}",headers=headers()).status_code==404
    assert client.post("/api/v1/companies",headers=headers(),json={"name":"Forged","organization_id":2}).status_code==422


def test_attachment_content_rechecks_membership_without_signed_urls(api,monkeypatch):
    client,engine=api
    from app.api.routes import attachments
    calls=[]
    def private_storage(method,path,**kwargs):
        calls.append(path)
        return b"private fixture bytes"
    monkeypatch.setattr(attachments,"storage",private_storage)
    response=client.get("/api/v1/attachments/1/download",headers=headers())
    assert response.json()=={"url":"/api/v1/attachments/1/content"}
    assert client.get(response.json()["url"],headers=headers()).content==b"private fixture bytes"
    assert client.get("/api/v1/attachments/2/content",headers=headers()).status_code==404
    with Session(engine) as db:
        db.scalar(sa.select(Membership).where(Membership.organization_id==1,Membership.user_id==1)).is_active=False;db.commit()
    assert client.get(response.json()["url"],headers=headers()).status_code==403
    assert len(calls)==1


def test_workflows_and_import_relationships_stay_in_tenant(api):
    client,engine=api
    body={"csv_text":"first,company,email\nCross,2,cross@example.com\n","mapping":{"first_name":"first","company_id":"company","email":"email"}}
    response=client.post("/api/v1/imports/contacts/preview",headers=headers(),json=body)
    assert response.status_code==200,response.text
    assert response.json()["invalid"]==1
    assert client.post("/api/v1/leads/1/convert",headers=headers(),json={"company_id":2,"create_deal":False}).status_code==422
    from app.api.routes.workspace import run_lead_workflows
    with TenantSession(engine) as db:
        db.info["organization_id"]=1
        run_lead_workflows(db,db.get(Lead,1))
    with Session(engine) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(Task).where(Task.organization_id==2))==1
        assert db.scalar(sa.select(sa.func.count()).select_from(Task).where(Task.organization_id==1))==2


def test_rollout_flag_and_session_schema_are_fail_closed(api,monkeypatch):
    client,engine=api
    monkeypatch.setattr(settings,"TENANT_ISOLATION_ENABLED",False)
    assert client.get("/api/v1/companies",headers=headers()).status_code==503
    with engine.connect() as db:
        inspector=sa.inspect(db)
        assert next(c for c in inspector.get_columns("auth_sessions") if c["name"]=="active_organization_id")["nullable"]
        assert any(fk["referred_table"]=="organizations" for fk in inspector.get_foreign_keys("auth_sessions"))


def test_recovery_session_cannot_read_crm_but_can_reset_before_tenant_selection(api,monkeypatch):
    client,engine=api
    from app.core.sessions import session_key,encrypt
    from app.api.routes import auth
    from app.core import sessions
    identity="00000000-0000-0000-0000-000000000001"  # Disposable test identity only.
    monkeypatch.setattr(settings,"AUTH_PROVIDER","supabase")
    def provider(method,path,*args,**kwargs):
        return {"id":identity} if (method,path)==("GET","/user") else {}
    monkeypatch.setattr(auth,"auth_request",provider)
    monkeypatch.setattr(sessions,"auth_request",provider)
    with Session(engine) as db:
        db.get(User,1).auth_user_id=identity
        db.add(AuthSession(id=session_key("fixture-recovery"),user_id=1,recovery=True,
            expires_at=datetime.now(timezone.utc)+timedelta(hours=1),access_token=encrypt("fixture-provider-token"),
            access_expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
        db.commit()
    client.cookies.set(settings.SESSION_COOKIE_NAME,"fixture-recovery",path="/api")
    assert client.get("/api/v1/companies",headers={"X-Organization-ID":"1"}).status_code==403
    assert client.post("/api/v1/auth/password",json={"password":"ValidPassword123!"}).status_code==200
    with Session(engine) as db:
        assert db.get(AuthSession,session_key("fixture-recovery")) is None
