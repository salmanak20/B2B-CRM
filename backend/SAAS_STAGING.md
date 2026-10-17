# Phase 7A verification and staging gate

Verified against Phase 6B `0c1ce2e` on `feature/multi-tenant-saas`.
No production connection, migration, deployment, bootstrap or billing activation.
Results: 246 focused backend checks, 40 desktop and 22 mobile Chromium checks
passed; frontend build, shipped-asset and known-private-credential scans passed.

## Reproduce isolated checks

From the repository root, use `backend/.venv/Scripts/python.exe
scripts/tenant_foundation_qa.py`, then run it separately with `--backfill`,
`--isolation`, `--team`, `--onboarding`, `--platform`, `--subscriptions`,
`--billing`, and `--integration`. Each invocation creates and removes its own
localhost PostgreSQL cluster; external credentials are replaced with test
sentinels. Providers are mocked. The cross-phase tests exercise paid entitlement
confirmation, workspace switching, suspension, data preservation and recovery.

The migration checks run the entire empty upgrade chain, preserve legacy rows
through SaaS upgrades/empty rollback/re-upgrade, and verify populated billing
rollback refuses data loss atomically. Never downgrade a populated staging or
production database to bypass these guards; preserve it and recover forward.

From the frontend directory, run `npm run build`, `npm run check`, and focused
`npx playwright test` selections for auth, companies, contacts, leads, deals,
tasks, dashboard, reports, navigation, integration, team, onboarding, platform,
subscriptions and billing. Use `--project=chromium`; repeat key flows with
`--project=mobile-chromium`. Include `tests/quality/responsive.spec.js` on desktop.
Browser persistence uses isolated SQLite; backend integration uses PostgreSQL.
Auth/email, platform and billing browser provider responses are mocked.

## Verified restored snapshot (2026-10-17)

Local PostgreSQL 18.4, `127.0.0.1:56039/crm_tenant_staging`, head
`a1b2c3d4e507`. Read-only verification matched the approved legacy fingerprint,
all prior counts and 297 FK edges. One legacy organization/membership retains
the sales representative role and absent Auth link; no owner was assigned.
The original pipeline, six stages and ten audit entries remain unchanged.
Tenant columns remain nullable, new private tables empty with RLS enabled.
The encrypted snapshot is dated 2026-10-15 and excludes managed Auth/Storage;
it is not a fresh production clone. PostgreSQL 17 compatibility remains untested
on this device (only PostgreSQL 18 is installed).

## Hosted preview blocked; existing project retained

Read-only Vercel access succeeds for `salman-yousafzais-projects/b2-b-crm`.
SSO deployment protection is enabled. Services route `/api/v1/*` to FastAPI and
other paths to Vite; frontend API requests remain same-origin. Startup runs no
migrations or seed. Automatic deployment of this branch remains disabled.
Only `VITE_API_BASE_URL` currently targets Preview; required backend variables
are production-only. No preview deployment was attempted.

Before deploying a protected Preview in this project, supply separate reachable
staging PostgreSQL, Supabase Auth and private Storage, with a strong staging
`JWT_SECRET_KEY`. Configure Preview-only `DATABASE_URL`, `ENVIRONMENT`,
`AUTH_PROVIDER`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`,
`SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `FRONTEND_URL`,
`CORS_ORIGINS`, `COOKIE_SECURE=true`, `DEBUG=false`, and explicit feature flags.
Use HTTPS and exact staging origins/redirects, host-only HttpOnly cookies and
verified private bucket access. Never expose privileged keys as `VITE_*`.

Keep registration/billing flags off until controlled staging validation; leave
production registration and live billing disabled. Live signup/invitation/recovery
emails and redirects, private upload/download, an explicitly approved verified
platform administrator, and Lemon Squeezy test store/variant mapping, checkout,
signed delivery and reconciliation remain pending. See `PLATFORM_ADMIN.md` and
`LEMON_BILLING.md`. No live identity or owner may be inferred from test fixtures.
