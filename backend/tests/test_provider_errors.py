"""Safe provider error classification without disclosing upstream response data."""
import httpx
import pytest
from fastapi import HTTPException
from app.core import provider


@pytest.mark.parametrize('code,path,status,message',[
    ('invalid_credentials','/token?grant_type=password',401,'Incorrect email or password'),
    ('session_not_found','/user',401,'session has ended'),
    ('session_not_found','/token?grant_type=refresh_token',401,'session has ended'),
    ('mfa_verification_failed','/factors/fixture/verify',422,'Authenticator code did not match'),
    ('mfa_challenge_expired','/factors/fixture/verify',422,'verification timed out'),
])
def test_documented_errors_have_actionable_safe_messages(monkeypatch,code,path,status,message):
    monkeypatch.setattr(provider.settings,'SUPABASE_URL','https://supabase.invalid')
    monkeypatch.setattr(provider.settings,'SUPABASE_PUBLISHABLE_KEY','isolated-fixture')
    monkeypatch.setattr(provider.httpx,'request',lambda *a,**k:httpx.Response(422,json={'error_code':code,'msg':'private upstream response must not escape'}))
    with pytest.raises(HTTPException) as result:provider.auth_request('POST',path)
    assert result.value.status_code==status and message in result.value.detail
    assert 'private upstream' not in result.value.detail


@pytest.mark.parametrize('admin,path,body,status',[
    (True,'/admin/users/fixture',{'error_code':'invalid_credentials'},400),
    (False,'/user',{'error_code':'unexpected','msg':'private upstream'},401),
    (False,'/token?grant_type=refresh_token',{'error_code':'invalid_credentials'},401),
])
def test_unknown_admin_and_unrelated_errors_stay_generic(monkeypatch,admin,path,body,status):
    monkeypatch.setattr(provider.settings,'SUPABASE_URL','https://supabase.invalid')
    monkeypatch.setattr(provider.settings,'SUPABASE_PUBLISHABLE_KEY','isolated-fixture')
    monkeypatch.setattr(provider.settings,'SUPABASE_SERVICE_ROLE_KEY','isolated-fixture')
    monkeypatch.setattr(provider.httpx,'request',lambda *a,**k:httpx.Response(400,json=body))
    with pytest.raises(HTTPException) as result:provider.auth_request('GET',path,admin=admin)
    assert result.value.status_code==status
    assert result.value.detail=='Unable to authenticate or complete this account operation.'
