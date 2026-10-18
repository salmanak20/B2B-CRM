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

## Phase 7A.4 — approval-ready configuration (2026-10-18)

Read-only recheck: `dd846f7` is pushed, PR #1 is Draft; that commit has no
reported GitHub checks/statuses. No failing check was returned, but this is not
a green CI result. No runtime code or dependency changes are required here.

### Production Auth delta — approval required, not applied

In production project `hazrihbiqsflnmlcycen` only:

| Setting | Current | Proposed |
| --- | --- | --- |
| Site URL | `http://localhost:3000` | `https://b2-b-crm.vercel.app` |
| Redirect allowlist | Empty | Only `https://b2-b-crm.vercel.app/login` |
| Allow new users to sign up | On | Off (`disable_signup=true`) |
| Confirm email | On | Keep on (`mailer_autoconfirm=false`) |
| Email provider | Enabled | Keep enabled for existing users |

The existing recovery and team services both redirect to `/login`; no new
`/auth/callback` route, wildcard, localhost or staging redirect is needed in
production. Keep CRM registration/onboarding verification and billing gates off.
Recovery and invitation templates currently use provider defaults; the dashboard
disables source editing without custom SMTP. Retain the documented default
`{{ .ConfirmationURL }}` link flow; do not hardcode tokens, tenant IDs or alternate
domains. Full production delivery/token exchange remains untested and needs
separate approval with explicitly approved recipients after configuration.

### Manual SMTP setup — provider/credentials and approval required

Choose a production sender/provider and supply its SMTP host, port, TLS mode,
username, password/API credential, verified From email and sender display name.
Use that provider's required TLS port (commonly STARTTLS/587 or TLS/465), not a
guessed server. Verify SPF/DKIM/DMARC and disable email link tracking that rewrites
one-use Auth links. Enter credentials only in the production Supabase SMTP
settings, then review templates, sending limits and approved-recipient tests.
Never add SMTP secrets to frontend variables or this repository. Use independent
credentials for each environment; staging continues built-in email, custom SMTP
off, and only the already approved team inbox. No email was sent in Phase 7A.4.

### Backup/restore plan — fresh capture requires separate approval

Both October 15 encrypted archives (three calendar days old in Asia/Karachi)
passed SHA-256 comparison, authenticated decryption and `pg_restore --list`.
They contain a `0aa836556f2a` public-schema snapshot, dumped from PG17.6 by
pg_dump18.4; the second metadata file records the later upgrade to `f8b3015a0001`,
which does not make its earlier dump a snapshot of that later revision.
No fresh backup or restore was executed. Prior restore evidence is on PG18.4;
archive listing is not a fresh PG17 restore rehearsal.

After explicit backup approval, verify the production target/revision securely,
then from `backend` run the existing backup-only operator command:

```powershell
.\.venv\Scripts\python.exe -m app.db.safe_migrate --backup-only --pg-bin "C:\Program Files\PostgreSQL\18\bin"
```

Protect the ignored encrypted archive, checksum/revision/count metadata and its
original encryption secret separately with restricted access. Arrange separately
approved Auth records and private Storage object/metadata coverage; a public-only
dump cannot recover those resources. Managed backups are unavailable on this
project's free plan; no paid upgrade is authorized.

For rehearsal, decrypt the approved archive in memory and feed it to `pg_restore`
with `--exit-on-error --no-owner --no-acl`, targeting a newly created isolated
localhost PG17 database only, with target credentials in its subprocess environment.
Never pipe binary dumps through PowerShell's text pipeline. Compare source
revision, IDs, content fingerprints, counts and FKs before running the complete
Alembic chain plus reviewed backfill there; disable external email/billing calls.
Do not restore customer Auth/Storage into synthetic hosted staging without approval.
Retain nullable tenant columns and unresolved-owner decisions. Recover forward or
roll application code back against compatible additive schema; populated SaaS
downgrades deliberately refuse data loss. A production restore/migration is never
part of backup approval and needs its own reviewed write barrier/recovery decision.

### Remaining checklist

- [x] Current isolated staging PG17.11/head `a1b2c3d4e507`, production PG17.6/
  `f8b3015a0001`, distinct Supabase project IDs and scoped Preview envs rechecked.
- [x] Staging test-billing flag is false; production flag absent/default false,
  with an additional production refusal in the existing provider adapter.
- [x] Existing local archives validated without connecting to production for
  capture, creating a backup or writing plaintext dumps.
- [ ] Supply the four billing variable names listed above and verified sandbox
  plan/product/variant configuration. Presence check found all four absent; no
  checkout/webhook/activation/cancellation/reconciliation attempt was made.
- [ ] Approve a second project-team inbox for live invitations; none is approved.
- [ ] Approve the exact production Auth delta above, choose/supply production
  SMTP settings, and approve specific delivery recipients/tests.
- [ ] Approve fresh encrypted backup scope/destination and isolated PG17 restore
  rehearsal, including a separate Auth/Storage recovery plan.
- [ ] Decide CAPTCHA/leaked-password protection and CI requirements; authorize
  any paid security option separately. No production change, deployment, main
  merge or Phase 7B work occurred.
