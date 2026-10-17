"""Test-only API adapter. Fixed API origin, sanitized errors and explicit object checks."""
from datetime import datetime,timedelta
from decimal import Decimal
from urllib.parse import urlsplit
import hashlib,hmac,json,secrets
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import settings
from app.core.sessions import utcnow,aware
from app.models import Organization,Membership
from app.models.subscription import Subscription,SubscriptionPlan
from app.models.billing import BillingCheckout,BillingEvent
from app.services.subscriptions import current,validate_capacity
from app.services.platform import lock_administration

SUB_EVENTS={'subscription_created','subscription_updated','subscription_cancelled','subscription_resumed','subscription_expired','subscription_paused','subscription_unpaused'}
PAY_EVENTS={'subscription_payment_success','subscription_payment_failed','subscription_payment_recovered','subscription_payment_refunded'}

def available():
    return bool(settings.ENVIRONMENT!='production' and settings.LEMON_SQUEEZY_TEST_ENABLED and settings.LEMON_SQUEEZY_TEST_API_KEY and settings.LEMON_SQUEEZY_TEST_STORE_ID and settings.LEMON_SQUEEZY_TEST_WEBHOOK_SECRET)

def enabled():
    if not available():raise HTTPException(503,'Lemon Squeezy test billing is not configured; live billing is disabled')

def numeric(value):
    value=str(value)
    if not value.isascii() or not value.isdigit() or len(value)>30:raise HTTPException(502,'Invalid provider resource identity')
    return value

def api(method,path,data=None,params=None):
    enabled()
    try:
        response=httpx.request(method,'https://api.lemonsqueezy.com/v1/'+path,
            headers={'Authorization':'Bearer '+settings.LEMON_SQUEEZY_TEST_API_KEY,'Accept':'application/vnd.api+json','Content-Type':'application/vnd.api+json'},
            json=data,params=params,timeout=20,follow_redirects=False)
        if not 200<=response.status_code<300:raise HTTPException(503,'Test billing provider unavailable; retry reconciliation later')
        return response.json()
    except (httpx.HTTPError,ValueError):raise HTTPException(503,'Test billing provider unavailable')

def resource(kind,identifier):
    identifier=numeric(identifier)
    obj=api('GET',kind+'/'+identifier).get('data',{})
    if obj.get('type')!=kind or str(obj.get('id'))!=identifier:raise HTTPException(502,'Unexpected billing provider response')
    return obj['attributes']

def test_object(attributes):
    if attributes.get('test_mode') is not True or str(attributes.get('store_id'))!=settings.LEMON_SQUEEZY_TEST_STORE_ID:
        raise HTTPException(400,'Only the configured test store is permitted')

def safe_url(url):
    value=urlsplit(url or '')
    if value.scheme!='https' or not value.hostname or not value.hostname.endswith('.lemonsqueezy.com') or value.username or value.password or value.port not in {None,443}:
        raise HTTPException(502,'Untrusted billing URL')
    return url

def mapping(plan):
    value=settings.LEMON_SQUEEZY_TEST_PLAN_IDS.get(plan.code,{})
    if not value.get('product_id') or not value.get('variant_id'):raise HTTPException(503,'Plan has no approved test provider mapping')
    return numeric(value['product_id']),numeric(value['variant_id'])

def verify_plan(plan):
    product_id,variant_id=mapping(plan)
    product=resource('products',product_id);test_object(product)
    variant=resource('variants',variant_id)
    if variant.get('test_mode') is not True or str(variant.get('product_id'))!=product_id:
        raise HTTPException(400,'Variant does not match the approved test product')
    prices=api('GET','prices',params={'filter[variant_id]':variant_id,'page[size]':1}).get('data',[])
    if not prices:raise HTTPException(503,'Provider subscription price is missing')
    price=prices[0]['attributes']
    store=resource('stores',settings.LEMON_SQUEEZY_TEST_STORE_ID)
    if (str(price.get('variant_id'))!=variant_id or price.get('category')!='subscription' or price.get('scheme')!='standard'
        or price.get('usage_aggregation') or price.get('renewal_interval_unit')!=plan.billing_interval or price.get('renewal_interval_quantity')!=1
        or store.get('currency')!=plan.currency or not isinstance(price.get('unit_price'),int) or price['unit_price']<0):
        raise HTTPException(503,'Provider price, currency or interval does not match this plan')
    if plan.price is not None and Decimal(price['unit_price'])!=plan.price*100:raise HTTPException(503,'Provider price differs from the approved internal price')
    return product_id,variant_id

def owner(db,user):
    org=user.organization_id
    db.scalar(select(Organization).where(Organization.id==org).with_for_update())
    member=db.scalar(select(Membership).where(Membership.organization_id==org,Membership.user_id==user.id).execution_options(populate_existing=True))
    if not member or not member.is_active or member.removed_at or member.role!='owner':raise HTTPException(403,'Organization owner billing access required')
    return org

def checkout(db,user,plan_id,request_key):
    enabled();org=owner(db,user)
    plan=db.get(SubscriptionPlan,plan_id)
    if not plan or not plan.published:raise HTTPException(404,'Published plan not found')
    sub=current(db,org)
    if sub and sub.external_subscription_id:raise HTTPException(409,'Use billing management for the existing subscription')
    validate_capacity(db,org,plan.seat_limit)
    row=db.scalar(select(BillingCheckout).where(BillingCheckout.organization_id==org,BillingCheckout.request_key==request_key))
    if row:
        if row.plan_id!=plan_id:raise HTTPException(409,'Checkout request was already used for another plan')
        if row.state=='ready' and aware(row.expires_at)>utcnow():return {'url':safe_url(row.checkout_url)}
        raise HTTPException(409,'Checkout requires reconciliation or has expired; use a new request after expiry')
    pending=db.scalar(select(BillingCheckout).where(BillingCheckout.organization_id==org,BillingCheckout.state.in_(['creating','ready','uncertain']),BillingCheckout.expires_at>utcnow()))
    if pending:raise HTTPException(409,'An organization checkout is already pending; reuse its original request')
    product_id,variant_id=verify_plan(plan)
    row=BillingCheckout(token=secrets.token_hex(32),organization_id=org,user_id=user.id,plan_id=plan.id,request_key=request_key,
        product_id=product_id,variant_id=variant_id,state='creating',expires_at=utcnow()+timedelta(minutes=30))
    db.add(row);db.commit()  # Retain intent on ambiguous network failure; never blindly create a second checkout.
    token=row.token
    try:
        result=api('POST','checkouts',{'data':{'type':'checkouts','attributes':{
            'test_mode':True,'expires_at':aware(row.expires_at).isoformat(),
            'product_options':{'enabled_variants':[int(variant_id)],'redirect_url':settings.FRONTEND_URL.rstrip('/')+'/subscription'},
            'checkout_data':{'email':user.email,'custom':{'billing_token':token}}},
            'relationships':{'store':{'data':{'type':'stores','id':settings.LEMON_SQUEEZY_TEST_STORE_ID}},'variant':{'data':{'type':'variants','id':variant_id}}}}})['data']
        a=result['attributes'];test_object(a)
        if str(a.get('variant_id'))!=variant_id:raise HTTPException(502,'Checkout variant mismatch')
        db.refresh(row)
        row.provider_checkout_id=result['id'];row.checkout_url=safe_url(a['url'])
        if row.state!='completed':row.state='ready'
        db.commit()
        return {'url':row.checkout_url}
    except Exception:
        db.rollback();row=db.get(BillingCheckout,token);row.state='uncertain';db.commit();raise

def date(value):
    try:return aware(datetime.fromisoformat(value.replace('Z','+00:00')))
    except (ValueError,TypeError,AttributeError):raise HTTPException(502,'Invalid provider timestamp')

def subscription_resource(identifier):
    a=resource('subscriptions',identifier);test_object(a);return a

def apply_subscription(db,sub,attributes,plan):
    updated=date(attributes['updated_at'])
    if sub.provider_updated_at and updated<aware(sub.provider_updated_at):raise HTTPException(503,'Provider state is stale; retry reconciliation')
    status=attributes['status'];start=date(attributes['created_at']);end=date(attributes['ends_at']) if attributes.get('ends_at') else None
    if status not in {'active','on_trial','past_due','unpaid','cancelled','expired','paused'}:raise HTTPException(502,'Unknown provider subscription status')
    # Never extend grace with webhook retries; anchor to first provider delinquency update.
    if status in {'past_due','unpaid'}:
        if sub.past_due_since is None:sub.past_due_since=updated
        end=aware(sub.past_due_since)+timedelta(days=max(0,min(settings.LEMON_SQUEEZY_GRACE_DAYS,30)))
        mapped='active' if end>utcnow() else 'expired'
    else:
        sub.past_due_since=None
        mapped={'active':'active','on_trial':'trialing','cancelled':'active' if end and end>utcnow() else 'expired','expired':'expired','paused':'paused'}[status]
    if end and end<=start:
        if mapped=='expired':end=None
        else:raise HTTPException(502,'Provider period is invalid')
    sub.plan_id=plan.id;sub.starts_at=start;sub.ends_at=end;sub.status=mapped;sub.enforcement_enabled=True
    sub.provider_status=status;sub.provider_updated_at=updated;sub.provider_order_id=numeric(attributes['order_id'])
    sub.external_customer_id='ls_test:'+numeric(attributes['customer_id'])

def webhook(db,raw,signature):
    enabled()
    expected=hmac.new(settings.LEMON_SQUEEZY_TEST_WEBHOOK_SECRET.encode(),raw,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected.encode(),(signature or '').encode()):raise HTTPException(401,'Invalid webhook signature')
    try:payload=json.loads(raw);event=payload['meta']['event_name'];data=payload['data'];rid=numeric(data['id'])
    except (ValueError,KeyError,TypeError):raise HTTPException(400,'Invalid webhook payload')
    if event not in SUB_EVENTS|PAY_EVENTS|{'order_refunded'}:return {'ignored':True}
    test_object(data.get('attributes',{}))
    lock_administration(db)
    digest=hashlib.sha256(raw).hexdigest()
    if db.get(BillingEvent,digest):return {'duplicate':True}
    if event in SUB_EVENTS:
        if data.get('type')!='subscriptions':raise HTTPException(400,'Webhook resource type mismatch')
        sid=rid
    elif event in PAY_EVENTS:
        if data.get('type')!='subscription-invoices':raise HTTPException(400,'Webhook resource type mismatch')
        invoice=resource('subscription-invoices',rid);test_object(invoice);sid=numeric(invoice['subscription_id'])
    else:
        if data.get('type')!='orders':raise HTTPException(400,'Webhook resource type mismatch')
        order=resource('orders',rid);test_object(order)
        known=db.scalar(select(Subscription).where(Subscription.provider_order_id==rid,Subscription.external_subscription_id.like('ls_test:%')))
        if not known:raise HTTPException(503,'Refund requires an established subscription binding')
        sid=known.external_subscription_id.split(':')[1]
    a=subscription_resource(sid)
    sub=db.scalar(select(Subscription).where(Subscription.external_subscription_id=='ls_test:'+sid))
    if sub:
        if sub.provider_status is None or sub.provider_updated_at is None:raise HTTPException(409,'Unverified provider binding requires administrator review')
        org=sub.organization_id
        if sub.external_customer_id!='ls_test:'+str(a.get('customer_id')):raise HTTPException(409,'Subscription customer binding mismatch')
    else:
        token=payload['meta'].get('custom_data',{}).get('billing_token')
        intent=db.get(BillingCheckout,token) if isinstance(token,str) else None
        if not intent or intent.state not in {'ready','uncertain','creating'}:raise HTTPException(409,'Unmatched checkout; manual review required')
        if str(a.get('variant_id'))!=intent.variant_id or str(a.get('product_id'))!=intent.product_id:
            raise HTTPException(409,'Checkout provider mapping mismatch')
        if not aware(intent.expires_at)-timedelta(minutes=30)<=date(a['created_at'])<=aware(intent.expires_at):
            raise HTTPException(409,'Subscription was created outside the trusted checkout period')
        org=intent.organization_id
    db.scalar(select(Organization).where(Organization.id==org).with_for_update())
    plan_matches=[]
    for plan in db.scalars(select(SubscriptionPlan)):
        try:product,variant=mapping(plan)
        except HTTPException:continue
        if (product,variant)==(str(a.get('product_id')),str(a.get('variant_id'))):plan_matches.append(plan)
    if len(plan_matches)!=1:raise HTTPException(409,'Provider plan mapping needs review')
    plan=plan_matches[0];verify_plan(plan)
    if not sub:
        initial_status=a.get('status')
        paid_period=initial_status=='cancelled' and a.get('ends_at') and date(a['ends_at'])>utcnow()
        if initial_status not in {'active','on_trial'} and not paid_period:
            raise HTTPException(409,'Initial billing binding awaits a verified active or trialing subscription')
        sub=current(db,org)
        if sub and sub.external_subscription_id:raise HTTPException(409,'Organization is already bound to another subscription')
        if not sub:sub=Subscription(organization_id=org);db.add(sub)
        sub.external_subscription_id='ls_test:'+sid
        intent.state='completed'
    # Existing seats are never removed, even after an external downgrade. New admissions
    # remain blocked until usage is within the new limit.
    apply_subscription(db,sub,a,plan)
    db.add(BillingEvent(digest=digest,event_name=event,resource_id=rid,received_at=utcnow()))
    db.commit();return {'ok':True}

def bound(db,org):
    sub=current(db,org)
    if not sub or sub.provider_status is None or sub.provider_updated_at is None or not (sub.external_subscription_id or '').startswith('ls_test:'):raise HTTPException(404,'No verified test billing subscription')
    sid=sub.external_subscription_id.split(':')[1];a=subscription_resource(sid)
    if 'ls_test:'+str(a.get('customer_id'))!=sub.external_customer_id:raise HTTPException(409,'Billing customer binding mismatch')
    return sid,a

def history(db,org,page):
    enabled();sid,a=bound(db,org)
    result=api('GET','subscription-invoices',params={'filter[subscription_id]':sid,'page[number]':page,'page[size]':20})
    rows=[]
    for obj in result.get('data',[]):
        invoice=obj['attributes'];test_object(invoice)
        if str(invoice.get('subscription_id'))!=sid or str(invoice.get('customer_id'))!=str(a['customer_id']):raise HTTPException(502,'Invoice ownership mismatch')
        rows.append({'id':obj['id'],'status':invoice['status'],'currency':invoice['currency'],'total_formatted':invoice['total_formatted'],
            'created_at':invoice['created_at'],'refunded':invoice.get('refunded',False),'refunded_amount_formatted':invoice.get('refunded_amount_formatted'),
            'invoice_url':safe_url(invoice['urls']['invoice_url']) if invoice.get('urls',{}).get('invoice_url') else None})
    return {'invoices':rows,'page':page}
