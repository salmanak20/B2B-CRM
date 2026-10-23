# Lemon Squeezy test billing

Live checkout is hard-disabled, including when `ENVIRONMENT=production`.
All flags default off; missing credentials disable external calls. Phase 6A
customers remain unchanged until they explicitly purchase through a trusted
test checkout and the signed webhook is independently reconciled.
Initial delinquent/paused/expired states cannot activate a new billing binding;
they require reconciliation to verified active/trial or a paid cancellation period.

Server-only configuration (blank names in `.env.example`):
`LEMON_SQUEEZY_TEST_ENABLED`, `LEMON_SQUEEZY_TEST_API_KEY`,
`LEMON_SQUEEZY_TEST_STORE_ID`, `LEMON_SQUEEZY_TEST_WEBHOOK_SECRET`,
`LEMON_SQUEEZY_TEST_PLAN_IDS`, `LEMON_SQUEEZY_GRACE_DAYS`.
The plan mapping is JSON: plan code -> `product_id`/`variant_id` string IDs.
Each variant must uniquely match one internal plan, a test product in the
configured store and a standard recurring Price with matching interval/currency.
Nullable internal prices are not populated or invented; configured prices must
match the provider. Metered/tiered pricing is outside this integration.

Configure a test webhook to `/api/v1/billing/webhook` for `subscription_created`,
`subscription_updated`, `subscription_cancelled`, `subscription_resumed`,
`subscription_expired`, `subscription_paused`, `subscription_unpaused`,
`subscription_payment_success`, `subscription_payment_failed`,
`subscription_payment_recovered`, `subscription_payment_refunded`, `order_refunded`.
Verify raw-body HMAC-SHA256 `X-Signature` before parsing/processing. Receipt hashes
and synchronized subscription changes commit together. No raw payload/card data
is persisted. Every event fetches authoritative provider objects; older fetched
versions fail for retry. Unknown bindings fail without changing access. If provider
retries are exhausted, resend the event after resolving the mapping; do not edit
entitlements from a redirect or event payload alone.

Checkout intents bind random server tokens to an organization, owner and plan.
An uncertain API response retains its intent and blocks new checkouts until its
30-minute provider expiry, preventing blind duplicate retries. An expired request
needs a new request UUID. A completed billing subscription uses provider management;
automatic replacement of an existing billing binding is intentionally refused.

Failed payments retain optional entitlements for seven days from the first
verified delinquent provider update (configurable 0–30 days). Repeated retries
never extend this anchor. Core CRM remains available after grace; recovery clears
delinquency. Cancellation retains access only until provider `ends_at`; expiration
and pauses restrict optional features. Refunds appear in actual provider invoice
history; they do not imply cancellation. Subscription state follows the provider.
Existing seats are never removed by downgrade; additional admissions are blocked
until active plus reserved seats fit. Suspension always remains authoritative.

Only current organization owners can checkout, read history or request portal URLs.
History validates each invoice's store/customer/subscription binding and paginates.
Customer portals can expose multiple subscriptions, so shared provider customers
are refused and require administrator-assisted management. Portal/checkout/invoice
URLs must be HTTPS on Lemon Squeezy domains; arbitrary provider links are not fetched.

Sandbox delivery/checkout/portal/refund verification remains pending until approved
test credentials, store, product/variant IDs and a reachable staging webhook exist.
Use an isolated test store and approved test identity, then verify all event types
and redirects before any separate request for live billing. No production change
or live activation is part of Phase 6B.

Contracts: [Checkout](https://docs.lemonsqueezy.com/api/checkouts/create-checkout),
[signatures](https://docs.lemonsqueezy.com/help/webhooks/signing-requests),
[events](https://docs.lemonsqueezy.com/help/webhooks/event-types),
[subscriptions](https://docs.lemonsqueezy.com/api/subscriptions/the-subscription-object),
[prices](https://docs.lemonsqueezy.com/api/prices/the-price-object).
