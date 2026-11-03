from uuid import UUID
from fastapi import APIRouter,Request,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field
from app.api.deps import SessionDep,CurrentActiveUser
from app.services import lemon_squeezy as lemon
from app.core.rate_limit import limit_auth
from sqlalchemy import select
from app.models.subscription import Subscription
from starlette.concurrency import run_in_threadpool

router=APIRouter(tags=['Test billing'])
class CheckoutInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    plan_id:int=Field(gt=0)
    request_key:UUID

@router.post('/billing/checkout')
def checkout(body:CheckoutInput,db:SessionDep,user:CurrentActiveUser,request:Request):
    limit_auth(db,request,str(user.id),'billing-checkout')
    return lemon.checkout(db,user,body.plan_id,str(body.request_key))

@router.post('/billing/portal')
def portal(db:SessionDep,user:CurrentActiveUser):
    lemon.enabled();org=lemon.owner(db,user);sid,a=lemon.bound(db,org)
    # Provider customer portals may expose every subscription of that customer.
    # Refuse shared customers rather than exposing another workspace's billing.
    shared=db.scalar(select(Subscription.id).where(Subscription.external_customer_id=='ls_test:'+str(a['customer_id']),Subscription.organization_id!=org))
    customer_id=lemon.numeric(a['customer_id'])
    remote=lemon.api('GET','customers/'+customer_id+'/subscriptions',params={'page[size]':2})
    orders=lemon.api('GET','customers/'+customer_id+'/orders',params={'page[size]':2})
    if (shared or len(remote.get('data',[]))!=1 or str(remote['data'][0]['id'])!=sid or remote.get('links',{}).get('next')
        or len(orders.get('data',[]))!=1 or str(orders['data'][0]['id'])!=str(a['order_id']) or orders.get('links',{}).get('next')):
        raise HTTPException(409,'Shared billing customer: contact the administrator for subscription management')
    return {'url':lemon.safe_url(a.get('urls',{}).get('customer_portal'))}

@router.get('/billing/history')
def history(db:SessionDep,user:CurrentActiveUser,page:int=Query(1,ge=1,le=10000)):
    lemon.enabled();org=lemon.owner(db,user);return lemon.history(db,org,page)

@router.post('/billing/webhook')
async def webhook(db:SessionDep,request:Request):
    raw=await request.body()
    if len(raw)>262144:raise HTTPException(413,'Webhook payload too large')
    return await run_in_threadpool(lemon.webhook,db,raw,request.headers.get('X-Signature',''))
