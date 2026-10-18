# Phase 7A.3 release gate — 2026-10-18

Production release remains blocked. Production configuration/data were read only;
no deployment, migration, signup, email or payment was executed there.

## Verified staging

- Dedicated `crm-saas-staging`, PostgreSQL 17.11, Alembic `a1b2c3d4e507`;
  protected existing Vercel Preview at Phase 7A.2 `869606f`, with green checks.
- The explicitly approved existing verified identity (CRM user 1) was bootstrapped
  through the guarded operator command. Organization roles/memberships unchanged.
- Real platform login, database-backed metrics, search, verified owner details,
  final-admin protection, suspension/session invalidation, reactivation, exact
  company preservation and platform audit passed. Desktop/mobile dashboard loaded.
  Platform privilege did not allow access to an unjoined workspace or suspended
  tenant records. Disposable fixtures were removed and test sessions logged out.
- Non-platform owners/admins remain denied in focused PostgreSQL tests; live
  owner denial was verified before bootstrap in Phase 7A.2. A second independent
  live identity remains unavailable. No extra Auth identity was invented.
- Employee invitation delivery/acceptance/role/revocation remains pending: no
  second authorized inbox approved; retained mocked tests are not live results.

## Billing configuration required (server-only, test store)

Absent from staging: `LEMON_SQUEEZY_TEST_API_KEY`, `LEMON_SQUEEZY_TEST_STORE_ID`,
`LEMON_SQUEEZY_TEST_WEBHOOK_SECRET`, `LEMON_SQUEEZY_TEST_PLAN_IDS` (internal plan
code to verified `product_id`/`variant_id` JSON). Supply genuine test products and
matching internal plans; then explicitly configure `LEMON_SQUEEZY_TEST_ENABLED`
for staging only. Checkout, signed delivery, activation, cancellation and
reconciliation remain pending. No live payment path was enabled.

## Production checks and decisions required

- Supabase Site URL is `http://localhost:3000`, with no allowed redirect URLs.
  Configure/verify the approved production HTTPS site and exact `/login` redirect
  in a separately authorized operation. No redirect was changed here.
- Custom SMTP is disabled; default templates apply. Built-in email is restricted
  to project-team inboxes and is not a production delivery service. Choose a
  production sender/SMTP provider, verify DNS/delivery and recovery/verification.
  Staging keeps built-in email and custom SMTP disabled as requested.
- CRM self-registration is off; onboarding/email-verification and test-billing
  flags are absent from production and default off in the SaaS configuration.
  Direct Supabase Auth signup is enabled (`disable_signup=false`): decide and
  explicitly authorize closing that provider path before public release.
- Cookies are configured Secure; exact HTTPS CORS, DEBUG=false, server-only secret
  names and distinct staging/production project IDs checked. Live production
  responses have HSTS, CSP, frame denial and nosniff. Branch auth rate limiting is
  database-backed; production Supabase signup/signin and token verification limits
  are 30 requests/5 min/IP. CAPTCHA and leaked-password protection are disabled.
  No custom Vercel firewall configuration was available (404); do not claim a
  custom WAF rule set was verified. No production load/abuse test was executed.
- Production remains at `f8b3015a0001`; zero unvalidated FKs and browser table
  grants. The free project has no managed backups. Local encrypted public-schema
  backups are dated 2026-10-15 and omit managed Auth/Storage. Before release,
  obtain a fresh encrypted backup, preserve its key separately, cover Auth/Storage,
  and rehearse restore + the complete SaaS migration/backfill on an isolated copy.
  Existing `app.db.safe_migrate` is operator-only; never downgrade populated SaaS
  tables or infer a Legacy owner. Production mapping approval remains separate.
- Dependency audits: zero known Python/npm vulnerabilities at this check.
  Known-secret scans found no matches in 43 built assets or six served production
  files. This is a bounded scan, not a guarantee against unknown secrets.
- Existing Vercel production deployment is unchanged; feature auto-deployment is
  disabled. Production bootstrap/release approval remains a separate task.

References: [SMTP restrictions](https://supabase.com/docs/guides/auth/auth-smtp),
[password protection](https://supabase.com/docs/guides/auth/password-security).
