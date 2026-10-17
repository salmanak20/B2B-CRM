# Subscription foundation (no payment provider)

Migration `a1b2c3d4e506` creates private tables only. No prices, plan records,
subscriptions, payments or invoices are generated; existing access is unchanged.
Platform administrators configure `starter`, `business`, `enterprise` via
`PUT /platform/plans/{code}`. Price may be null; currency and month/year interval
are explicit. Published plans appear at `/subscription`; changes require platform
authorization and an audit reason. Tenant responses omit external billing IDs.

`PUT /platform/subscriptions/{organization_id}` assigns a plan and status.
Enforcement defaults false and must be explicitly enabled. No subscription or
disabled enforcement preserves existing access. Enabled subscriptions apply seat
limits and explicit `analytics`, `exports`, `workflows`, `attachments` booleans.
Core CRM, settings and subscription access remain available; expired, future,
paused or canceled subscriptions deny these optional features and new seats.
Disabled workflows do not execute from lead changes. Suspension always takes
precedence. Owners/admins cannot assign plans or mutate billing status.

Active memberships count as seats; unexpired pending invitations reserve seats.
Inviting, accepting (consuming its reservation), activating, and changing plan
limits serialize on the organization row. Role changes never waive seat limits.
Downgrades below active plus reserved seats are rejected. Removing subscriptions
or payment-provider integration is outside this phase. Bootstrap remains manual
and requires an approved verified identity; none is granted by this migration.

Tests: `python scripts/tenant_foundation_qa.py --subscriptions`; isolated PostgreSQL
and mocked Auth only. No production changes or automatic billing activation.
