import {test,expect} from '@playwright/test';
async function setup(page,{bound=false,owner=true}={}){
  const writes=[];
  await page.route('https://example.lemonsqueezy.com/**',r=>r.fulfill({contentType:'text/html',body:'<h1>Test provider checkout</h1>'}));
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;
    if(req.method()==='POST'){
      writes.push({path,body:req.postDataJSON()});
      return route.fulfill({json:{url:'https://example.lemonsqueezy.com/'+(path.endsWith('/portal')?'billing':'checkout/custom/test')}});
    }
    const plan={id:1,name:'Starter',price:null,currency:'USD',billing_interval:'month',seat_limit:5,entitlements:{analytics:true}};
    const data=path.endsWith('/auth/me')?{id:1,name:'Owner',email:'owner@example.com',organization_id:1,role:{name:'admin'},organization_role:owner?'owner':'admin',preferences:{}}:
      path.endsWith('/workspace')?{name:'Business A',timezone:'UTC',currency:'USD'}:
      path.endsWith('/subscription/plans')?[plan]:
      path.endsWith('/subscription')?{plan:bound?plan:null,subscription:bound?{status:'active',enforcement_enabled:true,starts_at:'2026-10-17T00:00:00Z'}:null,seats:{active:1,pending:0,limit:5},entitlements:{analytics:true},test_billing_available:true,can_manage_billing:owner,provider_status:bound?'active':null}:
      path.endsWith('/billing/history')?{invoices:[{id:'11',status:'refunded',total_formatted:'$10.00',created_at:'2026-10-17T00:00:00Z',refunded_amount_formatted:'$10.00',invoice_url:'https://app.lemonsqueezy.com/invoice/test'}],page:1}:[];
    await route.fulfill({json:data});
  });
  return writes;
}
test('owner uses hosted test checkout without frontend entitlement mutation',async({page})=>{
  const writes=await setup(page);
  await page.goto('/subscription?success=true&plan_id=1');
  await expect(page.getByText('Current plan: Not configured')).toBeVisible();
  await page.getByRole('button',{name:'Test checkout: Starter'}).click();
  await expect(page).toHaveURL(/example\.lemonsqueezy\.com\/checkout\/custom\/test/);
  expect(writes.length).toBe(1);expect(writes[0].path).toBe('/api/v1/billing/checkout');
  expect(writes[0].body.plan_id).toBe(1);expect(writes[0].body.request_key).toMatch(/^[0-9a-f-]{36}$/);
  expect(Object.keys(writes[0].body).sort()).toEqual(['plan_id','request_key']);
});
test('verified billing history and portal use backend data',async({page})=>{
  const writes=await setup(page,{bound:true});
  await page.goto('/subscription');
  await expect(page.getByRole('heading',{name:'Provider billing history (test)'})).toBeVisible();
  await expect(page.getByRole('cell',{name:'refunded',exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:'Invoice',exact:true})).toHaveAttribute('href','https://app.lemonsqueezy.com/invoice/test');
  await page.getByRole('button',{name:'Manage test billing'}).click();
  await expect(page).toHaveURL(/example\.lemonsqueezy\.com\/billing$/);
  expect(writes.map(w=>w.path)).toEqual(['/api/v1/billing/portal']);
});
test('business administrators cannot use owner billing controls',async({page})=>{
  await setup(page,{owner:false});await page.goto('/subscription');
  await expect(page.getByRole('heading',{name:'Subscription',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:/Test checkout|Manage test billing/})).toHaveCount(0);
});
