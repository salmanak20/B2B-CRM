from datetime import datetime,timezone,timedelta
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from fastapi import HTTPException
from tests.test_tenant_isolation import api,isolation_engine,headers,FIXTURE_PASSWORD_HASH
from app.models import User,Role,Membership,Company
from app.models.invitation import OrganizationInvitation
from app.models.session import AuthSession
from app.services import team
from app.services.team import send_invitation as real_send_invitation


@pytest.fixture
def employees(api,monkeypatch):
    client,engine=api
    with Session(engine) as db:
        default=db.scalar(sa.select(Role.id).where(Role.name=="viewer"))
        for uid,role in ((4,"owner"),(5,"sales_manager"),(6,"sales_rep"),(7,"viewer")):
            db.add(User(id=uid,name=f"Employee {uid}",email=f"employee{uid}@example.com",password_hash=FIXTURE_PASSWORD_HASH,role_id=default,is_active=True));db.flush()
            db.add(Membership(organization_id=1,user_id=uid,role=role,is_active=True))
        for uid in (2,3):db.get(User,uid).auth_user_id=f"00000000-0000-0000-0000-{uid:012d}"
        db.commit()
        db.execute(sa.text("SELECT setval(pg_get_serial_sequence('users','id'),(SELECT max(id) FROM users))"));db.commit()
    calls=[]
    def send(email,name,existing):
        calls.append(email)
        return existing["auth_user_id"] if existing and existing["auth_user_id"] else ("00000000-0000-0000-0000-000000000003" if email=="user3@example.com" else "00000000-0000-0000-0000-000000000009")
    monkeypatch.setattr(team,"send_invitation",send)
    return client,engine,calls


@pytest.mark.parametrize("uid,status",[(1,200),(4,200),(5,403),(6,403),(7,403)])
def test_invitation_authority_and_no_early_access(employees,uid,status):
    client,engine,calls=employees
    response=client.post('/api/v1/team/invitations',headers=headers(user=uid),json={"name":"Candidate","email":"user3@example.com","role":"sales_rep"})
    assert response.status_code==status,response.text
    with Session(engine) as db:
        assert db.scalar(sa.select(Membership).where(Membership.organization_id==1,Membership.user_id==3)) is None
    assert len(calls)==(1 if status==200 else 0)


def test_cross_tenant_scope_and_body_injection_rejected(employees):
    client,_,calls=employees
    assert client.post('/api/v1/team/invitations',headers=headers(user=2,org=1),json={"name":"Candidate","email":"user3@example.com"}).status_code==403
    assert client.post('/api/v1/team/invitations',headers=headers(),json={"name":"Candidate","email":"user3@example.com","organization_id":2}).status_code==422
    assert client.put('/api/v1/team/members/4',headers=headers(user=2,org=2),json={"role":"viewer"}).status_code==404
    assert calls==[]


@pytest.mark.parametrize("path,body",[("/team/members/4",{"role":"viewer"}),("/team/members/6",{"role":"owner"})])
def test_admin_cannot_manage_owner_permissions(employees,path,body):
    client,_,_=employees
    assert client.put('/api/v1'+path,headers=headers(),json=body).status_code==403
    assert client.post('/api/v1/team/invitations',headers=headers(),json={"name":"Candidate","email":"user3@example.com","role":"owner"}).status_code==403


@pytest.mark.parametrize("method,path,body",[("put","/team/members/4",{"role":"admin"}),("put","/team/members/4",{"is_active":False}),("delete","/team/members/4",None)])
def test_final_owner_protected(employees,method,path,body):
    client,engine,_=employees
    assert client.request(method,'/api/v1'+path,headers=headers(user=4),json=body).status_code==409
    with Session(engine) as db:
        owner=db.scalar(sa.select(Membership).where(Membership.organization_id==1,Membership.user_id==4))
        assert owner.role=="owner" and owner.is_active and owner.removed_at is None


def test_legacy_routes_cannot_bypass_owner_safeguards(employees):
    client,engine,_=employees
    assert client.patch('/api/v1/users/4/status?is_active=false',headers=headers()).status_code==403
    with Session(engine) as db: role=db.scalar(sa.select(Role.id).where(Role.name=="viewer"))
    assert client.put('/api/v1/users/4',headers=headers(),json={"role_id":role}).status_code==403


def test_second_owner_and_safe_self_removal(employees):
    client,engine,_=employees
    assert client.put('/api/v1/team/members/6',headers=headers(user=4),json={"role":"owner"}).status_code==200
    assert client.delete('/api/v1/team/members/4',headers=headers(user=4)).status_code==200
    with Session(engine) as db:
        members=list(db.scalars(sa.select(Membership).where(Membership.organization_id==1,Membership.role=="owner",Membership.is_active.is_(True))))
        assert [m.user_id for m in members]==[6]


def test_accepted_invitation_preserves_other_organization_role(employees):
    client,engine,_=employees
    result=client.post('/api/v1/team/invitations',headers=headers(),json={"name":"Existing account","email":"user2@example.com","role":"sales_rep"})
    assert result.status_code==200,result.text
    invitation=result.json()["id"]
    assert client.get('/api/v1/team/invitations',headers=headers(user=2,org=2)).json()==[]
    assert client.delete(f'/api/v1/team/invitations/{invitation}',headers=headers(user=2,org=2)).status_code==404
    assert client.post(f'/api/v1/auth/invitations/{invitation}/accept',headers=headers(user=3,org=2)).status_code==404
    assert client.post(f'/api/v1/auth/invitations/{invitation}/accept',headers=headers(user=2,org=2)).status_code==200
    assert client.post(f'/api/v1/auth/invitations/{invitation}/accept',headers=headers(user=2,org=2)).status_code==409
    with Session(engine) as db:
        roles={m.organization_id:m.role for m in db.scalars(sa.select(Membership).where(Membership.user_id==2))}
        assert roles=={1:"sales_rep",2:"admin"}
        assert db.get(User,2).role.name=="admin"


def test_revocation_removes_only_organization_sessions_and_preserves_records(employees):
    client,engine,_=employees
    with Session(engine) as db:
        for org in (1,2):db.add(AuthSession(id=f"fixture-org-{org}",user_id=1,active_organization_id=org,expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
        db.commit()
    assert client.delete('/api/v1/team/members/1',headers=headers(user=4)).status_code==200
    assert client.get('/api/v1/companies',headers=headers()).status_code==403
    assert client.get('/api/v1/companies',headers=headers(org=2)).status_code==200
    with Session(engine) as db:
        assert db.get(AuthSession,"fixture-org-1") is None
        assert db.get(AuthSession,"fixture-org-2") is not None
        assert db.get(Company,1).owner_id==1
        assert db.get(User,1).is_active


def test_manager_assigns_only_active_organization_representatives(employees):
    client,_,_=employees
    assert client.put('/api/v1/leads/1',headers=headers(user=5),json={"owner_id":6}).status_code==200
    assert client.patch('/api/v1/tasks/1/assignee',headers=headers(user=5),json={"assigned_to_id":6}).status_code==200
    for target in (2,4,7):
        assert client.patch('/api/v1/tasks/1/assignee',headers=headers(user=5),json={"assigned_to_id":target}).status_code in {403,422}
    assert client.put('/api/v1/team/members/6',headers=headers(user=5),json={"role":"admin"}).status_code==403


def test_expired_or_revoked_invitation_cannot_grant_access(employees):
    client,engine,_=employees
    response=client.post('/api/v1/team/invitations',headers=headers(user=4),json={"name":"Candidate","email":"user3@example.com","role":"owner"})
    invitation=response.json()["id"]
    with Session(engine) as db:
        db.get(OrganizationInvitation,invitation).expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    assert client.post(f'/api/v1/auth/invitations/{invitation}/accept',headers=headers(user=3)).status_code==409
    assert client.get('/api/v1/auth/invitations',headers=headers(user=3)).json()==[]


def test_provider_failure_grants_no_membership(employees,monkeypatch):
    client,engine,_=employees
    def unavailable(*args):raise HTTPException(503,"Provider unavailable")
    monkeypatch.setattr(team,"send_invitation",unavailable)
    assert client.post('/api/v1/team/invitations',headers=headers(),json={"name":"Candidate","email":"user3@example.com"}).status_code==503
    with Session(engine) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(OrganizationInvitation))==0


def test_no_provider_configuration_fails_safely(employees):
    with pytest.raises(HTTPException) as error:
        real_send_invitation("candidate@example.com","Candidate",None)
    assert error.value.status_code==503


def test_verified_login_can_link_pending_recipient_without_granting_access(employees):
    client,engine,_=employees
    response=client.post('/api/v1/team/invitations',headers=headers(),json={"name":"Candidate","email":"user3@example.com"})
    assert response.status_code==200
    from app.api.routes.auth import linked_user
    from app.db.tenant_session import TenantSession
    with Session(engine) as db:
        db.get(User,3).auth_user_id=None;db.commit()
    identity={"id":"00000000-0000-0000-0000-000000000003","email":"user3@example.com","email_confirmed_at":"2026-10-16T00:00:00Z"}
    with TenantSession(engine) as db:
        user=linked_user(db,identity)
        assert user.id==3 and user.role.name=="admin"
        assert user.auth_user_id==identity["id"]
    with Session(engine) as db:
        assert db.scalar(sa.select(Membership).where(Membership.user_id==3)) is None


def test_inviter_revocation_invalidates_pending_access(employees):
    client,engine,_=employees
    result=client.post('/api/v1/team/invitations',headers=headers(),json={"name":"Candidate","email":"user3@example.com"})
    invitation=result.json()["id"]
    assert client.delete('/api/v1/team/members/1',headers=headers(user=4)).status_code==200
    assert client.post(f'/api/v1/auth/invitations/{invitation}/accept',headers=headers(user=3)).status_code==409
    with Session(engine) as db:assert db.get(OrganizationInvitation,invitation).status=="revoked"


def test_concurrent_owner_demotions_preserve_one_owner(employees):
    _,engine,_=employees
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace
    from app.db.tenant_session import TenantSession
    with Session(engine) as db:
        member=db.scalar(sa.select(Membership).where(Membership.user_id==6,Membership.organization_id==1))
        member.role="owner";member.permission_role_name="admin";db.commit()
    def demote(user_id):
        with TenantSession(engine) as db:
            db.info.update(organization_id=1,actor_id=user_id)
            try:
                team.change_member(db,SimpleNamespace(id=user_id),user_id,role="admin")
                db.commit();return 200
            except HTTPException as error:
                db.rollback();return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(demote,[4,6]))==[200,409]
    with Session(engine) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(Membership).where(Membership.organization_id==1,Membership.role=="owner",Membership.is_active.is_(True)))==1


def test_globally_disabled_inviter_cannot_authorize_acceptance(employees):
    client,engine,_=employees
    response=client.post('/api/v1/team/invitations',headers=headers(),json={"name":"Candidate","email":"user3@example.com"})
    with Session(engine) as db:db.get(User,1).is_active=False;db.commit()
    assert client.post(f'/api/v1/auth/invitations/{response.json()["id"]}/accept',headers=headers(user=3)).status_code==409


def test_ambiguous_identity_is_not_silently_mapped(employees):
    client,engine,calls=employees
    with Session(engine) as db:
        db.add(User(name="Ambiguous",email="USER3@EXAMPLE.COM",role_id=1,is_active=True,password_hash=FIXTURE_PASSWORD_HASH));db.commit()
    assert client.post('/api/v1/team/invitations',headers=headers(),json={"name":"Candidate","email":"user3@example.com"}).status_code==409
    assert calls==[]


def test_new_identity_requires_verified_email_and_explicit_acceptance(employees):
    client,engine,_=employees
    response=client.post('/api/v1/team/invitations',headers=headers(),json={"name":"New Employee","email":"new@example.com","role":"sales_manager"})
    assert response.status_code==200
    from app.api.routes.auth import linked_user
    from app.db.tenant_session import TenantSession
    identity={"id":"00000000-0000-0000-0000-000000000009","email":"new@example.com"}
    with TenantSession(engine) as db:
        with pytest.raises(HTTPException):linked_user(db,identity)
        identity["email_confirmed_at"]="2026-10-16T00:00:00Z"
        user=linked_user(db,identity);user_id=user.id
        assert user.role.name=="viewer"
    with Session(engine) as db:assert db.scalar(sa.select(Membership).where(Membership.user_id==user_id)) is None
    assert client.post(f'/api/v1/auth/invitations/{response.json()["id"]}/accept',headers=headers(user=user_id)).status_code==200
    with Session(engine) as db:
        assert db.scalar(sa.select(Membership).where(Membership.user_id==user_id)).role=="sales_manager"


def test_admin_cannot_cancel_owner_invitation(employees):
    client,_,_=employees
    response=client.post('/api/v1/team/invitations',headers=headers(user=4),json={"name":"Candidate","email":"user3@example.com","role":"owner"})
    invitation=response.json()["id"]
    assert client.delete(f'/api/v1/team/invitations/{invitation}',headers=headers()).status_code==403
    assert client.delete(f'/api/v1/team/invitations/{invitation}',headers=headers(user=4)).status_code==200
