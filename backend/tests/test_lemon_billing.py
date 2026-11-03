"""Sandbox API contracts only; no network, payments, real identities or card data."""
from uuid import uuid4
from datetime import timedelta
import copy,hashlib,hmac,json
import httpx,pytest,sqlalchemy as sa
from sqlalchemy.orm import Session
from tests.test_subscriptions import foundation,control,business,api,isolation_engine
from app.core.config import settings
from app.core.sessions import utcnow
from app.models import Membership
from app.models.subscription import Subscription
from app.models.billing import BillingCheckout,BillingEvent
from app.services import lemon_squeezy as lemon

@pytest.fixture
def billing(foundation,monkeypatch):
    client,engine,login,pid,_=foundation
    for k,v in {'LEMON_SQUEEZY_TEST_ENABLED':True,'LEMON_SQUEEZY_TEST_API_KEY':'contract-key','LEMON_SQUEEZY_TEST_STORE_ID':'1','LEMON_SQUEEZY_TEST_WEBHOOK_SECRET':'contract-signing-secret','LEMON_SQUEEZY_TEST_PLAN_IDS':{'starter':{'product_id':'10','variant_id':'101'}}}.items():monkeypatch.setattr(settings,k,v)
    with Session(engine) as db:
        m=db.scalar(sa.select(Membership).where(Membership.organization_id==1,Membership.user_id==1));m.role='owner';m.permission_role_name='admin';db.commit()
    calls=[];state={'mode':True,'customer':900,'invoices':[],'shared':False,'failure':False}
    def obj(kind,i,a):return {'type':kind,'id':str(i),'attributes':a}
    def request(method,url,**kwargs):
        path=url.removeprefix('https://api.lemonsqueezy.com/v1/');calls.append((method,path,kwargs))
        if path=='products/10':data=obj('products',10,{'test_mode':state['mode'],'store_id':1})
        elif path=='variants/101':data=obj('variants',101,{'test_mode':True,'product_id':10})
        elif path=='prices':data=[obj('prices',1001,{'variant_id':101,'category':'subscription','scheme':'standard','unit_price':1000,'renewal_interval_unit':'month','renewal_interval_quantity':1})]
        elif path=='stores/1':data=obj('stores',1,{'currency':'USD'})
        elif path=='checkouts':
            if state['failure']:raise httpx.ReadTimeout('Contract timeout')
            state['custom']=kwargs['json']['data']['attributes']['checkout_data']['custom']
            state['sub']={'store_id':1,'test_mode':True,'customer_id':900,'order_id':700,'product_id':10,'variant_id':101,'status':'active','created_at':utcnow().isoformat(),'updated_at':utcnow().isoformat(),'ends_at':None,'urls':{'customer_portal':'https://example.lemonsqueezy.com/billing'}}
            data=obj('checkouts','checkout-contract',{'store_id':1,'test_mode':True,'variant_id':101,'url':'https://example.lemonsqueezy.com/checkout/custom/contract'})
        elif path=='subscriptions/500':data=obj('subscriptions',500,copy.deepcopy(state['sub']))
        elif path=='customers/900/subscriptions':data=[{'type':'subscriptions','id':'500'}]+([{'type':'subscriptions','id':'501'}] if state['shared'] else [])
        elif path=='customers/900/orders':data=[{'type':'orders','id':'700'}]
        elif path=='subscription-invoices/11':data=obj('subscription-invoices',11,invoice())
        elif path=='orders/700':data=obj('orders',700,{'test_mode':True,'store_id':1})
        elif path=='subscription-invoices':data=[obj('subscription-invoices',11,i) for i in state['invoices']]
        else:raise AssertionError((method,path))
        return httpx.Response(200,json={'data':data})
    def invoice():
        return {'store_id':1,'test_mode':True,'subscription_id':500,'customer_id':900,'status':'paid','currency':'USD','total_formatted':'$10.00','created_at':utcnow().isoformat(),'refunded':False,'urls':{'invoice_url':'https://app.lemonsqueezy.com/invoice/contract'}}
    monkeypatch.setattr(lemon.httpx,'request',request)
    login(1)
    def checkout(key=None,extra=None):
        return client.post('/api/v1/billing/checkout',headers={'X-Organization-ID':'1'},json={'plan_id':pid,'request_key':key or str(uuid4()),**(extra or {})})
    def deliver(name='subscription_created',changes=None,signature=True):
        attrs=copy.deepcopy(state['sub'])
        kind='subscriptions';rid=500
        if name in lemon.PAY_EVENTS:attrs=invoice();kind='subscription-invoices';rid=11
        if name=='order_refunded':attrs={'store_id':1,'test_mode':True};kind='orders';rid=700
        payload={'meta':{'event_name':name,'custom_data':state['custom']},'data':obj(kind,rid,attrs)}
        if changes:changes(payload)
        raw=json.dumps(payload,sort_keys=True).encode()
        sig=hmac.new(settings.LEMON_SQUEEZY_TEST_WEBHOOK_SECRET.encode(),raw,hashlib.sha256).hexdigest() if signature else 'bad'
        return client.post('/api/v1/billing/webhook',content=raw,headers={'X-Signature':sig,'Content-Type':'application/json'})
    return client,engine,login,pid,state,calls,checkout,deliver,invoice

def test_checkout_contract_uses_trusted_mapping_test_mode_and_never_activates_from_redirect(billing):
    client,engine,_,_,state,calls,checkout,deliver,_=billing
    key=str(uuid4());r=checkout(key);assert r.status_code==200,r.text
    assert checkout(key).json()==r.json()
    posts=[c for c in calls if c[0]=='POST'];assert len(posts)==1
    attrs=posts[0][2]['json']['data']['attributes']
    assert attrs['test_mode'] is True and attrs['product_options']['enabled_variants']==[101]
    assert 'custom_price' not in attrs and 'organization_id' not in attrs['checkout_data']['custom']
    with Session(engine) as db:assert db.scalar(sa.select(Subscription)) is None
    assert client.get('/api/v1/subscription?success=true&plan_id=1',headers={'X-Organization-ID':'1'}).json()['subscription'] is None
    assert deliver().status_code==200
    with Session(engine) as db:
        sub=db.scalar(sa.select(Subscription));assert sub.organization_id==1 and sub.external_subscription_id=='ls_test:500' and sub.enforcement_enabled

def test_raw_signature_duplicate_and_out_of_order_events_reconcile_current_state(billing):
    _,engine,_,_,state,_,checkout,deliver,_=billing
    assert checkout().status_code==200
    assert deliver(signature=False).status_code==401
    first=deliver();assert first.status_code==200,first.text
    assert deliver().json()=={'duplicate':True}
    state['sub']['status']='cancelled';state['sub']['ends_at']=(utcnow()+timedelta(days=20)).isoformat();state['sub']['updated_at']=(utcnow()+timedelta(seconds=1)).isoformat()
    assert deliver('subscription_updated').status_code==200
    # Old event body cannot restore old state: authoritative GET is still cancelled.
    assert deliver('subscription_created',lambda p:p['data']['attributes'].update(status='active')).status_code==200
    with Session(engine) as db:assert db.scalar(sa.select(Subscription.provider_status))=='cancelled'

def test_failed_payment_grace_does_not_extend_and_recovery_restores_access(billing):
    client,engine,_,_,state,_,checkout,deliver,_=billing
    checkout();assert deliver().status_code==200
    state['sub'].update(status='past_due',updated_at=(utcnow()+timedelta(seconds=1)).isoformat())
    assert deliver('subscription_payment_failed').status_code==200
    with Session(engine) as db:first=db.scalar(sa.select(Subscription.past_due_since))
    state['sub']['updated_at']=(utcnow()+timedelta(seconds=2)).isoformat()
    assert deliver('subscription_updated').status_code==200
    with Session(engine) as db:
        sub=db.scalar(sa.select(Subscription));assert sub.past_due_since==first
        sub.starts_at=utcnow()-timedelta(days=30);sub.ends_at=utcnow()-timedelta(seconds=1);db.commit()
    assert client.get('/api/v1/dashboard/summary',headers={'X-Organization-ID':'1'}).status_code==403
    assert client.get('/api/v1/companies',headers={'X-Organization-ID':'1'}).status_code==200
    state['sub'].update(status='active',updated_at=(utcnow()+timedelta(seconds=3)).isoformat())
    assert deliver('subscription_payment_recovered').status_code==200
    assert client.get('/api/v1/dashboard/summary',headers={'X-Organization-ID':'1'}).status_code==200

@pytest.mark.parametrize('status,expected',[('active','active'),('on_trial','trialing'),('paused','paused'),('expired','expired'),('unpaid','active')])
def test_provider_lifecycle_states(billing,status,expected):
    _,engine,_,_,state,_,checkout,deliver,_=billing
    checkout();assert deliver().status_code==200
    state['sub']['status']=status;state['sub']['updated_at']=(utcnow()+timedelta(seconds=1)).isoformat()
    if status=='expired':state['sub']['ends_at']=(utcnow()+timedelta(seconds=1)).isoformat()
    result=deliver('subscription_updated');assert result.status_code==200,result.text
    with Session(engine) as db:assert db.scalar(sa.select(Subscription.status))==expected

def test_real_provider_history_refunds_and_shared_customer_portal_protection(billing):
    client,_,_,_,state,_,checkout,deliver,invoice=billing
    checkout();assert deliver().status_code==200
    assert client.post('/api/v1/billing/portal',headers={'X-Organization-ID':'1'}).status_code==200
    state['invoices']=[{**invoice(),'status':'refunded','refunded':True,'refunded_amount_formatted':'$10.00'}]
    assert deliver('subscription_payment_refunded').status_code==200
    assert deliver('order_refunded').status_code==200
    response=client.get('/api/v1/billing/history',headers={'X-Organization-ID':'1'});assert response.status_code==200,response.text
    assert response.json()['invoices'][0]['status']=='refunded'
    assert 'card' not in response.text and 'user_email' not in response.text
    state['shared']=True
    assert client.post('/api/v1/billing/portal',headers={'X-Organization-ID':'1'}).status_code==409
    state['invoices'][0]['subscription_id']=501
    assert client.get('/api/v1/billing/history',headers={'X-Organization-ID':'1'}).status_code==502

def test_checkout_and_history_require_owner_and_current_organization(billing):
    client,engine,login,pid,_,_,checkout,deliver,_=billing
    assert checkout(extra={'organization_id':2}).status_code==422
    checkout();assert deliver().status_code==200
    assert client.get('/api/v1/billing/history',headers={'X-Organization-ID':'2'}).status_code==403
    login(2)
    assert client.post('/api/v1/billing/checkout',json={'plan_id':pid,'request_key':str(uuid4())}).status_code==403
    assert client.get('/api/v1/billing/history').status_code==403
    with Session(engine) as db:assert db.scalar(sa.select(sa.func.count()).select_from(Subscription))==1

def test_missing_config_live_objects_and_production_are_disabled(billing,monkeypatch):
    _,engine,_,_,state,calls,checkout,_,_=billing
    state['mode']=False;assert checkout().status_code==400
    assert not any(c[0]=='POST' for c in calls)
    monkeypatch.setattr(settings,'LEMON_SQUEEZY_TEST_API_KEY','');assert checkout().status_code==503
    monkeypatch.setattr(settings,'LEMON_SQUEEZY_TEST_API_KEY','contract');monkeypatch.setattr(settings,'ENVIRONMENT','production')
    assert lemon.available() is False
    with pytest.raises(Exception):lemon.enabled()

def test_ambiguous_checkout_failure_retains_intent_and_blocks_duplicate_charge(billing):
    _,engine,_,_,state,calls,checkout,_,_=billing
    state['failure']=True;key=str(uuid4());assert checkout(key).status_code==503
    assert checkout(key).status_code==409 and checkout().status_code==409
    assert len([c for c in calls if c[0]=='POST'])==1
    with Session(engine) as db:assert db.scalar(sa.select(BillingCheckout.state))=='uncertain'

def test_unmatched_live_payload_wrong_variant_and_stale_provider_fail_safely(billing):
    _,engine,_,_,state,_,checkout,deliver,_=billing
    checkout()
    assert deliver(changes=lambda p:p['meta']['custom_data'].update(billing_token='unknown')).status_code==409
    # Mutation above changes the test custom mapping; restore the stored trusted token.
    with Session(engine) as db:state['custom']={'billing_token':db.scalar(sa.select(BillingCheckout.token))}
    assert deliver(changes=lambda p:p['data']['attributes'].update(test_mode=False)).status_code==400
    state['sub']['variant_id']=999;assert deliver().status_code==409
    state['sub']['variant_id']=101;assert deliver().status_code==200
    state['sub']['updated_at']=(utcnow()-timedelta(days=1)).isoformat()
    assert deliver('subscription_updated').status_code==503
    with Session(engine) as db:assert db.scalar(sa.select(sa.func.count()).select_from(BillingEvent))==1

def test_seat_limits_and_provider_managed_status_cannot_be_bypassed(billing):
    client,_,login,pid,_,_,checkout,deliver,_=billing
    checkout();assert deliver().status_code==200
    assert client.put('/api/v1/team/members/4',headers={'X-Organization-ID':'1'},json={'is_active':True}).status_code==200
    assert client.put('/api/v1/team/members/5',headers={'X-Organization-ID':'1'},json={'is_active':True}).status_code==409
    login(3)
    result=client.put('/api/v1/platform/subscriptions/1',json={'plan_id':pid,'status':'active','reason':'Manual override'})
    assert result.status_code==409

def test_renewal_cancellation_and_expiration_follow_verified_provider(billing,monkeypatch):
    client,engine,_,_,state,_,checkout,deliver,_=billing
    checkout();assert deliver().status_code==200
    state['sub']['updated_at']=(utcnow()+timedelta(seconds=5)).isoformat()
    assert deliver('subscription_payment_success').status_code==200
    end=utcnow()+timedelta(days=1)
    state['sub'].update(status='cancelled',ends_at=end.isoformat(),updated_at=(utcnow()+timedelta(seconds=6)).isoformat())
    assert deliver('subscription_cancelled').status_code==200
    assert client.get('/api/v1/dashboard/summary',headers={'X-Organization-ID':'1'}).status_code==200
    from app.services import subscriptions
    monkeypatch.setattr(subscriptions,'utcnow',lambda:end+timedelta(seconds=1))
    assert client.get('/api/v1/dashboard/summary',headers={'X-Organization-ID':'1'}).status_code==403
    state['sub'].update(status='expired',updated_at=(utcnow()+timedelta(seconds=7)).isoformat())
    assert deliver('subscription_expired').status_code==200
    with Session(engine) as db:assert db.scalar(sa.select(Subscription.status))=='expired'

def test_zero_grace_and_failed_receipt_roll_back_safely(billing,monkeypatch):
    _,engine,_,_,state,_,checkout,deliver,_=billing
    checkout()
    from app.db.tenant_session import TenantSession
    from fastapi import HTTPException
    def fail(db,*args):
        if any(isinstance(o,BillingEvent) for o in db.new):raise HTTPException(503,'Receipt unavailable')
    sa.event.listen(TenantSession,'before_flush',fail)
    try:assert deliver().status_code==503
    finally:sa.event.remove(TenantSession,'before_flush',fail)
    with Session(engine) as db:
        assert db.scalar(sa.select(Subscription)) is None
        assert db.scalar(sa.select(BillingCheckout.state))=='ready'
    state['sub']['updated_at']=state['sub']['created_at']
    assert deliver().status_code==200
    monkeypatch.setattr(settings,'LEMON_SQUEEZY_GRACE_DAYS',0)
    state['sub'].update(status='unpaid',updated_at=state['sub']['created_at'])
    assert deliver('subscription_updated').status_code==200
    with Session(engine) as db:assert db.scalar(sa.select(Subscription.status))=='expired'

def test_concurrent_duplicate_events_commit_one_receipt(billing):
    _,engine,_,_,state,_,checkout,_,_=billing
    checkout()
    from concurrent.futures import ThreadPoolExecutor
    from app.db.tenant_session import TenantSession
    raw=json.dumps({'meta':{'event_name':'subscription_created','custom_data':state['custom']},'data':{'type':'subscriptions','id':'500','attributes':state['sub']}}).encode()
    sig=hmac.new(settings.LEMON_SQUEEZY_TEST_WEBHOOK_SECRET.encode(),raw,hashlib.sha256).hexdigest()
    def process(_):
        with TenantSession(engine,autoflush=False) as db:return lemon.webhook(db,raw,sig)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(process,range(2)))
    assert sum(bool(r.get('duplicate')) for r in results)==1
    with Session(engine) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(BillingEvent))==1
        assert db.scalar(sa.select(sa.func.count()).select_from(Subscription))==1

def test_initial_unpaid_checkout_preserves_legacy_access_until_payment_verified(billing):
    client,engine,_,_,state,_,checkout,deliver,_=billing
    checkout();state['sub']['status']='unpaid'
    assert deliver().status_code==409
    with Session(engine) as db:
        assert db.scalar(sa.select(Subscription)) is None
        assert db.scalar(sa.select(BillingEvent)) is None
    assert client.get('/api/v1/exports/companies',headers={'X-Organization-ID':'1'}).status_code==200
    state['sub']['status']='active'
    assert deliver().status_code==200

def test_manually_entered_external_ids_are_not_verified_provider_bindings(billing):
    client,engine,login,pid,_,_,checkout,deliver,_=billing
    checkout();login(3)
    result=client.put('/api/v1/platform/subscriptions/1',json={'plan_id':pid,'status':'active','reason':'Future identifier placeholder','external_subscription_id':'ls_test:500','external_customer_id':'ls_test:900'})
    assert result.status_code==200,result.text
    login(1)
    assert client.post('/api/v1/billing/portal',headers={'X-Organization-ID':'1'}).status_code==404
    assert deliver().status_code==409
    with Session(engine) as db:
        assert db.scalar(sa.select(Subscription.provider_status)) is None
        assert db.scalar(sa.select(BillingEvent)) is None
