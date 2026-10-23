"""Supabase MFA using the existing encrypted server session. No browser bearer tokens."""
from uuid import UUID
from fastapi import APIRouter, Request, Response, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.api.deps import SessionDep, CurrentUser
from app.services.platform import authorize, audit
from app.core.sessions import decrypt, set_provider_tokens, revoke_user_sessions
from app.core.provider import auth_request
from app.core.rate_limit import limit_auth
from app.core.config import settings

router=APIRouter(prefix='/auth/platform',tags=['Platform authentication'])


def session_for(db,request,user):
    authorize(db,request,user,require_mfa=False)
    return request.state.auth_session


@router.get('/mfa')
def status(db:SessionDep,request:Request,user:CurrentUser):
    session=session_for(db,request,user)
    identity=auth_request('GET','/user',token=decrypt(session.access_token))
    factors=[{'id':f['id'],'name':f.get('friendly_name','Authenticator')} for f in identity.get('factors',[]) if f.get('status')=='verified' and f.get('factor_type')=='totp']
    try: authorize(db,request,user)
    except HTTPException as error:
        if error.status_code!=403: raise
        ready=False
    else: ready=True
    return {'ready':ready,'factors':factors,'required':settings.PLATFORM_MFA_REQUIRED}


@router.post('/mfa/enroll')
def enroll(db:SessionDep,request:Request,response:Response,user:CurrentUser):
    session=session_for(db,request,user)
    limit_auth(db,request,user.email,'platform-mfa-enroll')
    response.headers['Cache-Control']='no-store'
    identity=auth_request('GET','/user',token=decrypt(session.access_token))
    if any(f.get('status')=='verified' for f in identity.get('factors',[])):
        raise HTTPException(409,'Use an existing verified factor; additional factors require separate review')
    result=auth_request('POST','/factors',{'factor_type':'totp','friendly_name':'CRM Platform Authenticator'},token=decrypt(session.access_token))
    audit(db,user.id,'platform_mfa_enrollment_started',user.id,'User requested authenticator enrollment')
    db.commit()
    return {'id':result['id'],'secret':result['totp']['secret'],'uri':result['totp']['uri']}


class Verification(BaseModel):
    model_config=ConfigDict(extra='forbid')
    factor_id:UUID
    code:str=Field(pattern=r'^\d{6}$')


@router.post('/mfa/verify')
def verify(body:Verification,db:SessionDep,request:Request,user:CurrentUser):
    session=session_for(db,request,user)
    limit_auth(db,request,user.email,'platform-mfa-verify')
    token=decrypt(session.access_token)
    path='/factors/'+str(body.factor_id)
    challenge=auth_request('POST',path+'/challenge',{},token=token)
    result=auth_request('POST',path+'/verify',{'challenge_id':challenge['id'],'code':body.code},token=token)
    if result.get('user',{}).get('id')!=user.auth_user_id:
        raise HTTPException(401,'MFA identity mismatch')
    set_provider_tokens(session,result)
    db.flush()
    authorize(db,request,user)
    audit(db,user.id,'platform_mfa_verified',user.id,'Authenticator challenge verified')
    db.commit()
    return {'ok':True}


@router.post('/sessions/revoke')
def revoke(db:SessionDep,request:Request,response:Response,user:CurrentUser):
    authorize(db,request,user)
    session=request.state.auth_session
    auth_request('POST','/logout?scope=global',token=decrypt(session.access_token))
    audit(db,user.id,'platform_sessions_revoked',user.id,'User revoked all provider and application sessions')
    revoke_user_sessions(db,user.id)
    response.delete_cookie(settings.SESSION_COOKIE_NAME,path='/api',secure=settings.COOKIE_SECURE,httponly=True,samesite='lax')
    return {'ok':True}
