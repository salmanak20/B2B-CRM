# Phase 7A.3 release gate — 2026-10-18

**Current launch decision (2026-10-19): payment-free, manually approved access.**
Lemon Squeezy is postponed and preserved. Its credentials and live sandbox tests
are no longer prerequisites for this launch. Keep `LEMON_SQUEEZY_TEST_ENABLED`
false; production billing is additionally refused by the adapter. Historical
billing blockers below describe the earlier paid-launch plan; the Phase 7A.8
go/no-go checklist and the latest phase below supersede them.
Phase 7A.9 below supersedes the historical Pilot implementation deferral.

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

## Phase 7A.5 — approved public backup rehearsal (2026-10-18)

The user explicitly approved read-only public CRM capture and local PG17 restore,
including restriction of `backend/.backups` to the current Windows user and
SYSTEM. Folder inheritance is disabled; all backup files' ACLs were verified.
No production data was accessed before that approval in this phase.

- A fresh public-only encrypted backup was created from production revision
  `f8b3015a0001`, using the existing `app.db.safe_migrate --backup-only` path.
  Source inventory and pg_dump shared an exported REPEATABLE READ / READ ONLY
  snapshot; `default_transaction_read_only=on` also guarded source connections.
  Encryption, SHA-256 and archive listing passed. No plaintext dump was saved.
- Restore into disposable local PG17.11 matched all 22 original tables' complete
  row fingerprints, column inventory and archive-declared constraints. Hashes
  include original IDs, timestamps, ownership and business values; raw rows and
  credentials were neither printed nor committed. Private evidence stays beside
  the encrypted archive. Source extension metadata was recorded; the public
  archive required no additional extensions. This does not validate restoration
  of Supabase-managed extensions, Auth or Storage, which were excluded.
- Only the disposable copy was upgraded from `f8b3015a0001` through all seven SaaS
  revisions to `a1b2c3d4e507`. Original business values remained identical; 101 FK
  relationships had no orphans and no FK was unvalidated. New SaaS tables stayed
  empty; tenant columns stayed nullable. No legacy mapping, owner assignment or
  production migration was executed. Populated downgrade was not attempted.
- PG17 used the pinned existing official image
  `postgres@sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3`,
  random loopback-only port, random local credentials and tmpfs data. No app server
  ran; migration processes used invalid provider sentinels and disabled external
  integrations. An internal-only Docker network initially prevented host access;
  the successful retry used a local bridge with loopback port publication and
  reused the same encrypted archive, without another production capture. All
  owned restore containers/networks were removed after verification.
- Two focused existing PG17 tests passed: the production registration rollout
  gate and refusal of missing/live/production billing configuration. Providers
  were mocked in these tests; no sandbox checkout, email or payment was attempted.

Repeat only under new capture approval: restrict/verify backup ACLs first; validate
the approved production project; export a read-only snapshot and use it for both
the inventory and `pg_dump --format=custom --schema=public --no-owner --no-acl
--snapshot=EXPORTED_SNAPSHOT`. Encrypt its captured bytes in memory with the
existing tool and retain private provenance. Authenticate/decrypt in memory for
`pg_restore --exit-on-error --no-owner --no-acl` into a fresh local PG17 database;
verify complete original-row fingerprints and schema before locally rehearsing
Alembic upgrades. Never use `--apply` against production, restore into an existing
customer database, run pytest fixtures against restored customer rows, or replace
the separate Auth/Storage recovery plan with a public-only archive.

### Current go/no-go — NO-GO for production

- [x] Fresh approved public backup, restricted local storage and successful PG17
  restore/additive migration rehearsal; no production writes/configuration change.
- [x] Branch/remote/PR verified at `b3a9b04` before this documentation update;
  PR #1 remains Draft. No checks/statuses were reported for that commit.
- [x] Production app registration flags remain off/absent-default-off and Preview
  test billing remains false. The adapter additionally refuses production billing.
- [ ] Direct production Supabase signup was still enabled at the last Auth check:
  application gates alone do not close that public provider path. Approve the
  exact HTTPS Site URL, sole `/login` redirect and signup restrictions above;
  retain email confirmation. No production Auth setting was changed here.
- [ ] SMTP provider/host/port/TLS, username/password, verified From address/name
  and DNS/delivery verification remain missing; approve configuration and exact
  test recipients. Staging custom SMTP stays off and uses its approved inbox only.
- [ ] All four Lemon Squeezy test variables listed above remain absent by name
  inspection; billing verification stopped. No second invitation inbox is approved.
- [ ] Confirm independent retention of the backup's original encryption secret;
  separately approve Auth/Storage backup scope/storage and recovery rehearsal.
- [ ] Review a production legacy-mapping/write-barrier/recovery plan against this
  fresh snapshot, decide CI and password-protection requirements, and separately
  authorize any production configuration, migration or release. This backup
  approval does not authorize any of those actions or Phase 7B.

## Phase 7A.6 — CI repair and complete recovery planning

- Missing-check cause verified: GitHub Actions is enabled, but the repository had
  no workflows and no runs/checks for `cbd5a18`. Feature Vercel auto-deployment is
  intentionally disabled; it stays disabled. Absent checks were not green CI.
- Added `.github/workflows/saas-checks.yml`: branch pushes and main-target PRs,
  including Drafts, run focused isolated PG17 backend checks and frontend
  build/shipped-asset checks. Actions/image are pinned, token access is contents
  read-only, credentials are not persisted, and only synthetic fixture/provider
  sentinels are used. No deployment or production secret is part of CI.
- Local workflow-equivalent checks passed: 72 isolation, three integration and
  22 bootstrap/pooling/rollout guards; frontend build/shipped checks passed.
  Hosted GitHub run results must be checked after push and reported separately.
- The exact production Auth delta remains the table above: HTTPS production
  Site URL, sole exact `/login` redirect, signup off, confirmation on and existing
  email login retained. The user approved this plan for separate execution;
  nothing is applied in Phase 7A.6. Public provider signup is not claimed closed.
- Production SMTP was rechecked read-only and remains disabled. Provider,
  host/port/TLS, username/password, verified From/name, DNS and approved delivery
  tests remain required. No provider/sender identity was invented or email sent.
- All four test-billing variable names remain absent; test flag remains false.
  Live checkout/webhook tests and live invitations remain pending; no second
  authorized staging inbox is approved. No live payment path was enabled.
- [Complete recovery plan](SAAS_RECOVERY_PLAN.md) now covers PostgreSQL, existing
  Auth identities/configuration, private Storage bytes/metadata/access controls,
  keys/retention, explicit legacy mappings, validation and rollback limitations.
  The documented October 18 public backup/PG17 rehearsal remains valid evidence;
  a new approved pre-cutover backup is required for future customer writes.

**NO-GO:** pending separate execution of the approved Auth plan, SMTP/delivery, sandbox configuration,
second approved inbox, independent key retention, Auth/Storage capture/restore
approval, current production mappings/write barrier and security/recovery policy.
CI success does not authorize production changes, PR merge or Phase 7B execution.

## Phase 7A.7 — external configuration recheck

- `76bba20` is pushed; both existing CI runs have all four jobs green. Protected
  Preview remains READY at runtime commit `869606f`. Read-only staging checks
  confirmed the separate project, PG17.11/head `a1b2c3d4e507`, private attachment
  bucket and zero unvalidated FKs. SSO preview protection remains enabled.
- No new billing configuration was found. The four `LEMON_SQUEEZY_TEST_*` names
  listed above are absent from both branch Preview and the ignored staging file;
  the test flag is false. No store/products could be verified, so no external
  checkout or webhook attempt was made. Live billing remains disabled.
- Staging custom SMTP is still disabled, retaining the approved built-in email
  setup. The completed approved-inbox signup/recovery evidence is retained; no
  new provider/delivery result is claimed and no repeat email was sent. Production
  SMTP configuration/delivery remains pending. No second authorized invitation
  inbox is approved, so live invitation acceptance/roles/revocation remains pending.
- The user explicitly chose to keep Auth/Storage recovery pending in this phase.
  No export, restore, signing-key access or recovery-resource provisioning occurred.
  The earlier public-only PG17 rehearsal remains separate evidence; full recovery
  scope/destination, independent key retention and Auth/Storage validation are open.
- Reviewed the approved staging legacy manifest: all 15 tenant-table assignments
  are represented, approval provenance exists, user 1 retains `sales_rep`, and
  Legacy owners remain empty. This review does not reconcile the manifest against
  new production data. Fresh production mapping signoff remains pending; no
  membership, Auth link, owner or business record was changed.
- The approved production Auth plan is unchanged: HTTPS production Site URL,
  sole exact `/login` redirect, signup off and confirmation on. No separate
  execution authorization was supplied or production configuration applied.
- Two focused existing PG17 rollout/missing-billing guards passed with synthetic
  data and mocked providers; no full local QA phase was repeated. These checks
  do not establish live provider delivery, sandbox processing or recovery success.

**NO-GO:** external configuration was not newly available. Supply verified test
billing credentials/store/products/mappings, production SMTP setup and approved
delivery tests, and a second explicitly approved staging inbox. Auth/Storage
recovery stays pending by user choice. The approved Auth plan still awaits
separate execution; current production mapping/recovery and pre-cutover backup
approvals remain open. Existing broad QA is retained, not re-labelled as new live
external verification. No production mutation, deployment, merge or Phase 7B.

## Phase 7A.8 — payment-free launch preparation (2026-10-19)

- Existing billing routes/models and future sandbox controls are retained.
  Checkout, portal, history and webhooks refuse disabled billing, even with
  credentials present. Unsigned requests cannot change subscriptions. Startup
  does not require billing credentials. Disabling billing does not alter plans,
  entitlements, memberships or seats; existing legacy access remains unchanged.
- Subscription UI labels online payments postponed and directs business-access
  requests to platform administration. Disabled billing displays no checkout or
  payment actions. Missing/enforcement-disabled seat limits no longer claim an
  automatic unlimited plan. Future explicitly enabled test controls are retained.
- Reuse audited `/platform/plans/{code}`, `/platform/subscriptions/{org_id}` and
  `/platform/organizations/{org_id}` controls; only verified platform admins may
  configure a manual subscription or reactivate a suspended workspace. Business
  owners/admins cannot approve themselves. No new subscription system, seeded
  plan, production price or automatic premium entitlement was introduced.

### Manual access policy and operator gate — implementation deferred

The user approved Free Pilot terms: five users including the owner, analytics,
exports, workflows and secured attachments; 30 days from platform-admin approval,
no automatic renewal, then read-only/export access if safely supported or a clear
expiry suspension. Only platform admins may activate/extend access. These terms
are not implemented: staging has no configured plan rows (no available IDs or
entitlements), and current expiry leaves core CRM writable. After reporting that
incompatibility, the user explicitly chose **keep policy implementation pending**.
No plan was created or access/expiry behavior changed. Existing subscriptions with
enforcement off or absent preserve legacy compatibility; they are **not** a
new-business approval policy. A null seat limit means no enforced cap and must
not be selected as a launch default without approval.

For an individually authorized, verified new workspace, keep it suspended
during review using the existing platform control. After policy approval,
configure the approved plan and subscription (`enforcement_enabled=true`,
explicit status/start/end, reason), validate active plus reserved seats and
feature access, then reactivate as a separate explicit platform-admin action.
Record the verified creator/membership without adopting or promoting a Legacy
owner. No such organization or subscription was created in hosted staging or
production by this phase; automated checks use disposable synthetic fixtures.

Public registration must remain off. Existing onboarding, when enabled, creates
an active workspace; suspension/reactivation is not an automatic approval queue.
Do not enable public onboarding for this manual launch. Operator intake and the
new-business activation procedure remain release gates until policy is approved.
Current expiry behavior preserves core CRM, denies optional features and new
seat admissions for an expired enforced subscription; it does not suspend the
organization or erase data. It does not satisfy the approved Pilot cutoff. Reusing
the existing Starter code/model for a five-seat Free Pilot plus clear expiry
denial was proposed; implementation is deferred, not authorized by this checklist.

### Payment-free go/no-go checklist

- [x] Branch/remote and Draft PR #1 verified at `1a38eb3`; eight prior CI checks
  passed. No production deployment, migration, mutation or email performed.
- [x] Read-only environment check: branch Preview has billing false and isolated
  Supabase/storage settings. Production registration is false/default-off and
  test billing absent/default-off. Protected synthetic staging registration
  remains separate from public production registration; settings were not edited.
- [x] 27 focused PG17 backend tests passed: plan/seat/feature enforcement,
  platform-only manual controls, owner/viewer
  restrictions, suspension/reactivation, cross-tenant denial and disabled payment
  paths validated with synthetic PG17 tests; test limits are not launch policy.
- [x] 14 desktop/mobile subscription/platform and retained future-billing
  browser contracts, build and shipped-asset checks passed. Provider tests are
  mocked/local; no hosted preview update or live provider test is claimed.
- [ ] Resume only on user instruction: implement the approved Pilot terms using
  the existing plan/subscription system, enforce expiry safely and validate the
  intake/activation procedure before admitting businesses. Implementation is
  explicitly pending; approval of policy terms is not a completed access gate.
- [ ] Separately authorize execution of the approved production Auth plan:
  `https://b2-b-crm.vercel.app`, sole exact `/login` redirect, provider signup off,
  confirmation on. The previously observed direct-provider signup path is not
  claimed closed. Application registration remains disabled.
- [ ] Production SMTP: choose provider/host/port/TLS, credentials, verified sender
  and DNS/delivery checks. Only the previously approved staging team inbox may
  receive test email. No second inbox exists; live employee invitations pending.
- [ ] Auth/private Storage recovery remains pending by user decision. Approve
  scope/destination and provider-supported rehearsal; confirm independent signing/
  encryption-key retention, custodians, retention, RPO/RTO and recovery policy.
- [ ] Reconcile current legacy account/Auth links, roles and all record mappings
  against a fresh approved snapshot, with no assumed owner. Obtain fresh
  pre-release encrypted backup/write-barrier approval. Retain the October 18
  public-only PG17 rehearsal and additive-schema rollback limitations described
  in [the recovery plan](SAAS_RECOVERY_PLAN.md); it is not full Auth/Storage recovery.
- [ ] Separate production platform-admin identity/bootstrap, migration/release,
  abuse-protection decisions and final go/no-go approval remain required.

**NO-GO for production:** Pilot implementation/intake, Auth/SMTP/invitation verification,
complete recovery/key retention, current mappings and fresh backup/release
approvals remain open. Billing credentials, sandbox checkout and live payments
are explicitly deferred, not payment-free launch blockers. No deployment,
production configuration change, PR merge or Phase 7B is authorized here.

## Phase 7A.9 — approved Free Pilot implementation (2026-10-19)

- Created staging plan **ID 1**, code `free_pilot`, through the existing platform
  API with the approved verified staging administrator. Free (USD 0 metadata),
  five users including owner, all four existing feature entitlements. Repeated
  configuration and an independent read-only query verified one identical plan.
  Existing subscriptions, memberships and business record counts were unchanged.
  No automatic production seed, schema migration or new billing system.
- Platform UI: use **Details** to review verified owner IDs, then **Free Pilot**
  to explicitly approve that owner and a reason. The existing subscription API
  re-verifies the owner/Auth link and platform session, enforces five seats,
  fixes dates server-side to 30 days from approval and audits the action. Existing
  non-Pilot subscriptions cannot be replaced. Separate business suspension is
  preserved; use the existing explicit Reactivate action after review if needed.
- Activation retries do not move dates. Renewal requires explicit **Approve
  30 days** with the previously observed expiry; stale/concurrent retries fail.
  Renewal starts a new 30-day period from that approval, with no automatic renewal
  or hidden extension. Only platform admins can configure/activate/renew it.
- Approved expiry fallback: block the Pilot workspace entirely with a clear
  expired/inactive message, including reads/exports. Selective read-only/export
  mode was not safely supported by existing feature/worker authorization.
  CRM writes, invitations/acceptance, uploads, workflows and tenant workers are
  blocked by fresh checks in request membership and the tenant-session boundary.
  A generic organization Reactivate does not renew an expired Pilot. Data,
  memberships and audits are retained; existing non-Pilot access is unchanged.
- Expired workspaces are not auto-selected on login, so a verified platform admin
  can still sign in to renew them. Reminder processing skips denied organizations
  and continues eligible ones. Billing code remains inactive and preserved;
  billing flags cannot disable Pilot expiry or grant unlimited access.
- Passed **149 focused PostgreSQL 17 checks**: 16 Pilot, 18 subscriptions, three
  payment-free, 72 tenant isolation, 26 onboarding and 14 platform tests. Provider
  calls in those tests are mocked; the hosted staging plan configuration above
  used real verified Auth. Only failed/new Pilot checks were repeated after test
  contract corrections and worker coverage; compatibility suites were retained.
- Passed **20 desktop/mobile Playwright contracts**, build and shipped-asset
  checks. Added an isolated Pilot CI matrix job. Final commit/CI is verified on
  PR #1 after push. New runtime/UI code is not deployed to the hosted Preview;
  browser and lifecycle tests used disposable/local staging, not customer data.

**Production remains NO-GO:** separately authorize approved production Auth
configuration, configure SMTP and approved delivery, approve a second staging
invitation inbox, validate Auth/private Storage recovery and independent key
retention, reconcile current Legacy mappings without inventing an owner, and
approve a fresh pre-release backup/write barrier and production administrator/
release plan. Protected hosted Preview deployment/live Pilot UI validation
remains a separate staging step. Payments and public production registration stay
disabled. No production access/configuration/data change, deployment, email or PR
merge occurred in Phase 7A.9. No existing customer subscription was assigned.

## Phase 7A.10 — hosted Pilot validation (2026-10-19)

- With explicit staging deployment approval, deployed exact `86dcb6b` to existing
  protected Preview `dpl_52CPwr44Ys5D4Yn3twii673DzRMT`, READY, target Preview/null,
  existing feature alias. SSO protection remains enabled; branch auto-deployment
  remains disabled. Production deployment/configuration were not changed.
- Confirmed branch-scoped staging Auth/private Storage settings, real backend
  readiness, isolated PG17.11/head `a1b2c3d4e507` and Free Pilot ID 1. No migration
  or payment credentials were required. All 12 source-commit CI checks passed.
- Using the approved existing verified staging administrator, created two
  disposable workspaces through hosted onboarding. Live approval granted five-seat
  configuration (owner counted), all four entitlements and exactly 30 days.
  Duplicate activation preserved dates. Explicit admin renewal restored access;
  duplicate renewal failed without extending it again.
- Hosted companies, contacts, leads, tasks, activities, pipelines/deals, dashboard,
  export and persistence checks passed. Cross-workspace record/reference and file
  access were denied. Viewer-role simulation used the same approved identity in
  a disposable workspace; its original owner role was restored afterward.
- Subscription UI passed at 1440/390 widths; expired UI displayed the clear
  fallback error. Checkout and unsigned webhooks returned disabled responses.
  Harness CSV/status/fixture/context/timing corrections were required; no product
  regression or source-code fix was established. Initial short UI waits expired
  while hosted requests were still loading; no performance benchmark is claimed.
- Controlled expiry affected only the tagged fixture subscription. Stale-session
  reads, writes, exports, workflow access, invitations, uploads and private file
  access were denied. Real private Storage upload/download passed; the object
  survived expiry/renewal and was then removed. CRM records/memberships remained.
- Reminder and workflow entrypoints, invoked locally against the isolated staging
  database, both rejected expired Pilot access. Dates and retirement were restored;
  no hosted scheduler was enabled or claimed tested. Test sessions logged out and
  disposable organizations were suspended; their synthetic CRM/audits retained.
- **Still pending:** a second approved independent identity/inbox for live employee
  invitation/acceptance, real multi-user five-seat admission and non-platform
  owner/employee renewal denial. Existing isolated backend tests cover those
  permissions/capacity paths; they are not new live independent-identity results.
  No new identity, email, real payment or customer subscription change occurred.

**Production NO-GO remains:** separately authorize production Auth execution;
configure SMTP and approved delivery; approve an independent invitation inbox;
validate Auth/Storage recovery and independent key retention; approve current
Legacy account/record mappings without inventing owners; approve a fresh
pre-cutover encrypted backup/write barrier and explicit production deployment.
No merge, production migration/configuration change or release is authorized.

## Phase 7A.11 — security evidence and release approval package (2026-10-19)

- Protected Preview remains READY at runtime `86dcb6b`; staging is PG17.11/head
  `a1b2c3d4e507`, private Storage, distinct staging Auth. No deployment/configuration
  change in this phase. Branch Preview billing and due-worker flags remain false.
- **71 focused PG17 tests passed:** 24 Pilot, 18 subscription, 26 organization-team
  and three payment-free tests. New independent fixture-account tests verify all
  five roles, cross-organization employee denial, forbidden subscription/entitlement
  administration, revoked existing cookies, five active seats including owner,
  sixth-member rejection and concurrent activation yielding one success/one conflict.
- Existing focused cases also verify reservation/acceptance races, manager-only
  team functions, four feature entitlements, final-owner protection, platform-only
  approval/renewal, stale-session expiry, preserved data and unchanged legacy/
  non-Pilot subscriptions. Duplicate renewal keeps one outcome (stale retry 409),
  never a second extension. No permissions were weakened and no regression found.
- **20 desktop/mobile browser contracts passed** for platform/subscription access,
  manual approval/renewal, expiry UI and disabled payment actions. Providers and
  browser APIs are mocked here; Phase 7A.10 remains the actual hosted evidence.
  Real delivery/independent hosted inbox tests are still pending. No emails sent.
- Retain the verified expired reminder/workflow entrypoint results from 7A.9/10.
  No safe hosted scheduler is configured (`DUE_NOTIFICATIONS_ENABLED=false`);
  **hosted scheduled execution remains pending**, not a passed test. No scheduler
  or live billing was enabled. Existing Lemon Squeezy code remains preserved.

### Separate production approvals required — nothing applied

1. **Auth execution:** approve the separate change window for Site URL
   `https://b2-b-crm.vercel.app`; sole allowed redirect
   `https://b2-b-crm.vercel.app/login`; `disable_signup=true`,
   `mailer_autoconfirm=false`, email login retained. Keep application signup and
   billing off. This is the previously approved plan, not newly applied settings
   or a fresh production inspection. No wildcard/staging/localhost redirect.
2. **SMTP/delivery:** select provider, host, port/TLS, username/secret, verified
   From address/name and DNS (SPF/DKIM/DMARC). Keep stage/production credentials
   separate and one-use-link tracking off. Approve exact production recipients
   before recovery/confirmation/invitation delivery and token-exchange tests.
   Only the existing staging inbox is approved; a second invitation inbox is not.
3. **Recovery set:** approve encrypted PostgreSQL capture/storage and isolated PG17
   restore; separately approve Auth UUID/password/configuration recovery and private
   Storage bytes/metadata/policies recovery into named isolated destinations.
   Public-schema rehearsal does not cover Auth identities or object bytes.
4. **Keys/retention:** select independent secure vault/custodians, retention,
   RPO/RTO and decryption/restore verification for backup/app encryption material.
   Record provider signing-key identifiers and supported recovery/rotation; do not
   assume managed private signing keys are exportable or copy them without approval.
5. **Legacy mapping:** reconcile fresh snapshot IDs, existing Auth links, roles,
   memberships and shared/orphan records. Legacy ownership stays unassigned;
   historical user 1 `sales_rep` approval is not a fresh production reconciliation.
   No new owner, Auth identity or production platform admin may be inferred.
6. **Cutover/rollback:** approve write barrier and a fresh encrypted pre-cutover
   recovery set, mapping validation and release operator/window. Populated SaaS
   downgrade guards prohibit blind rollback; prefer compatible additive schema/
   forward repair. Older restores can lose newer data/identities and need explicit
   recovery-point approval. See [recovery plan](SAAS_RECOVERY_PLAN.md).

**NO-GO:** those approvals/configuration and delivery/recovery evidence remain
open, including explicit verified production admin identity/bootstrap and final
deployment authorization. Hosted independent-inbox testing and scheduler execution
remain pending; isolated security verification is complete for the cases above.
No production data/configuration access or mutation, Auth/Storage export, key
copy, migration, deployment, payment, merge or Phase 7B occurred.


## Phase 7A.12 — final operational approval gates (2026-10-19)

**NO-GO: approval package prepared; production remains unchanged.** This section
supersedes historical status above. No deployment, migration, email, recovery
export, key copy, billing activation or owner assignment occurred.

### Production Auth — freshly inspected, execution still separate

Read-only dashboard inspection of `hazrihbiqsflnmlcycen` confirms the following.
Apply only during a separately approved configuration window; retain email login,
existing identities and passwords. No application registration flag is enabled.

| Setting | Observed / rollback baseline | Approved target |
| --- | --- | --- |
| `site_url` | `http://localhost:3000` | `https://b2-b-crm.vercel.app` |
| `uri_allow_list` | Empty | `https://b2-b-crm.vercel.app/login` only |
| `disable_signup` | `false` | `true` |
| `mailer_autoconfirm` | `false` | Keep `false` |
| `external_email_enabled` | `true` | Keep `true` |

Recovery and invitations already request `/login`; no wildcard or extra callback
is required. Templates remain provider defaults; custom SMTP is OFF. Before the
approved change, re-read these five fields and stop if the baseline differs.
Save a non-secret baseline and apply only this delta. Check settings read-back and
existing-account login; delivery/token exchange requires recipient approval.
On regression, pause release and obtain rollback authorization: restore the exact
five baseline values above through Auth settings, read back, and verify login.
Restoring the old signup/localhost settings reintroduces known gaps; never do so
automatically or treat rollback as launch-ready. No user deletion, password reset,
session/key rotation or database rollback is part of this Auth change.

### SMTP — production delivery blocked

No provider, sender domain, sender identity or production recipient is selected.
Compatible options include Resend, AWS SES and Postmark; selection is pending.
Supply `smtp_host`, `smtp_port`, `smtp_user`, `smtp_pass`, `smtp_admin_email`
(verified From) and `smtp_sender_name`; use verified TLS/465 or STARTTLS/587 per
provider, with certificate validation. For example only, Resend documents
`smtp.resend.com`, username `resend`, API key as SMTP password, 465 implicit TLS
or 587 STARTTLS. This example does not select/provision a provider.

Verify a user-controlled sender domain with the provider's exact SPF and DKIM DNS
records and an approved DMARC policy at `_dmarc.<sender-domain>`; retain one SPF
policy and merge mechanisms where necessary. Record actual DNS names/values only
after selecting the domain/provider. `vercel.app` hosting supplies neither an
approved sender domain nor an outbound SMTP account. Keep credentials independent
of staging and server-side; disable tracking that rewrites single-use links.

After separate setup approval, allow only exact production `/login` redirects,
review default recovery/invitation confirmation links, and verify delivery, token
exchange, password update and invitation acceptance with approved recipients.
Only the existing approved staging inbox may receive staging signup/recovery;
no second invitation inbox or production test recipient is approved. No emails
were sent here. Built-in Supabase SMTP remains staging-only, team-address-limited
and unsuitable for production; live email onboarding/recovery stays blocked.
Sources: [Supabase SMTP](https://supabase.com/docs/guides/auth/auth-smtp),
[Resend SMTP](https://resend.com/docs/send-with-smtp).

### Recovery and legacy reconciliation — approval package

- Retain the approved October 18 public-only PG17.11 rehearsal: 22 restored table
  fingerprints matched; upgrade through `a1b2c3d4e507` preserved original values
  and checked 101 FK relationships. This proves neither full Auth/Storage recovery
  nor freshness. Refresh the encrypted recovery set immediately before cutover,
  after an approved write barrier, with isolated restore/migration validation.
- Approve named isolated Auth/Storage destinations, encrypted capture scope,
  operator and recovery boundary. Preserve Auth UUIDs/links/password recovery
  material through supported methods, Auth settings, private object bytes and
  checksums, bucket metadata/policies/grants. Do not replay managed DDL blindly.
- Select independent secure archive/key storage, custodians, retention/deletion,
  RPO/RTO and a verified decryption drill. Preserve original backup/app encryption
  key versions. Record provider issuer/key IDs and supported recovery/rotation;
  do not assume managed signing private keys can be exported. Re-login may be
  required. These approvals and Auth/Storage validation remain pending.
- Fresh production public-metadata reconciliation used a REPEATABLE READ,
  explicitly READ ONLY transaction, rolled back after SELECTs. Revision remains
  `f8b3015a0001`; organization, membership, plan and subscription tables do not
  exist yet. One active legacy CRM user has no Auth link. Tenant inventory:
  one shared pipeline, six stages, 13 audit rows; all other 12 tenant tables empty.
  Twenty non-null FK edges and all populated polymorphic references resolved.
  All 20 tenant rows lack organization assignments under the old schema.
- Compared with the prior approved staging manifest, only three audit IDs are new;
  none are missing. The exact IDs, role/link state, audit relationships and proposed
  assignments remain in ignored local
  `backend/.tenant-staging/phase7a12-reconciliation.private.json`, SHA-256
  `801acfc08e2fc15257c54e19538b4d238f8d76ca7f61924defa1174394f14df2`.
  Customer rows/identifiers are not included in this tracked checklist.
- Approve that snapshot-specific proposal before migration: one Legacy Organization,
  existing role/active/ownership/link state preserved, shared configuration/history
  assigned only as reviewed, no owner. Separately verify and approve any existing
  Auth identity link and any production platform administrator; staging privileges
  confer no production approval. Reconcile again at cutover and stop on changes.
  Existing customer access must be verified before tenant enforcement is enabled.
- Follow [recovery plan](SAAS_RECOVERY_PLAN.md): populated downgrade guards must not
  be bypassed. Prefer compatible additive-schema code rollback or forward repair.
  Restoring older data can lose subsequent writes/identities and needs explicit
  recovery-point approval; no automatic reverse migration or customer deletion.

### Scheduler and deployment gates

A hosted scheduler is **not required for the initial Pilot security lifecycle**:
expiry is checked using server time on protected requests and tenant database
entrypoints, including stale sessions. Renewal is manual, never scheduled.
Lead workflows execute on CRM events; due notifications can be generated when
fetched or explicitly checked. Periodic cleanup is housekeeping, not the session
expiry authorization check. Keep `DUE_NOTIFICATIONS_ENABLED=false`; autonomous
scheduled reminders are not promised/tested. Retain prior expired worker-entrypoint
evidence; any later scheduled service needs its own staging execution approval.

Vercel metadata confirms distinct production/staging Supabase projects; production
`DATABASE_URL`, `JWT_SECRET_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_URL`,
`SUPABASE_PUBLISHABLE_KEY`, bucket and frontend URL names exist. Sensitive values
were redacted, not decrypted; presence does not establish validity/key recoverability.
Production Secure cookies/DEBUG=false and registration/due-worker=false remain set.
Business-registration, verified-email, test-billing and tenant-enforcement variables
are absent in production and default OFF in branch code; release must explicitly
review that manifest after mapping approval. Preview test billing remains false.
The provider adapter refuses production billing; no checkout/webhook or credentials
are required for this launch. Existing Pilot activation/extension requires platform
admin authorization and a verified approved owner; no policy/source change here.

Baseline `aca70f7` has all 12 CI checks green; PR #1 remains Draft. Two focused
release gates passed on disposable PG17.11 (production registration safety and
billing refusal); `git diff --check` passed. This is a documentation-only update;
completed hosted/security audits were not repeated. New-commit CI is reported in PR #1.
Final release remains NO-GO until separately approved Auth execution, SMTP/sender/
recipients and live delivery, second invitation inbox, complete recovery/keys,
snapshot-specific mapping/identity approvals, fresh backup/write barrier and an
explicit migration/deployment window. No Phase 7B action is authorized.

## Private existing-user Pilot decision — 2026-10-20

**NO-GO remains.** This scope supersedes earlier requirements to complete SMTP
and invitation delivery before an **existing-user-only private Pilot**. Resend is
preferred later, after obtaining a verified sender domain. Custom domain, SMTP,
new-user invitations and email recovery are deferred; authentication verification,
tenant controls, recovery-set readiness and individual execution approvals are not.
No runtime code, production setting, customer identity or ownership changes here.

### Feasibility and provisioning limits

- Existing confirmed Supabase email/password identities can authenticate without
  sending email. CRM additionally requires an active linked CRM account; tenant
  access requires approved active membership, an unsuspended organization and valid
  enforced Pilot access. An Auth account alone grants no CRM membership or role.
  This is code/documentation verification, not a newly executed production login.
- Latest read-only production reconciliation found one unlinked legacy CRM account
  and no SaaS organization/membership tables. No eligible production cohort or
  administrator has been approved. Preserve that account, its role, all records
  and relationships; no inferred email link or Legacy owner assignment.
- The existing no-email identity-link option accepts an explicit Auth UUID in
  `POST /api/v1/users/{user_id}/invite`; it checks confirmed matching provider email,
  preserves the existing CRM account and audits/revokes sessions. It requires an
  authorized tenant administrator and an existing suitable membership context, so
  it cannot bootstrap production or resolve an unapproved legacy mapping.
- Team invitations always call provider `/invite` or `/otp`. Auth admin creation
  is a server-only provider capability independent of public signup; it does not
  establish mailbox ownership, a CRM link, membership or workspace access. Never
  set `email_confirm=true` merely because a person was commercially approved.
- There is **no approved end-to-end no-email new-user provisioning procedure** in
  the current CRM. Minimum prerequisites for a later separately reviewed procedure:
  independently prove identity and mailbox control; approve exact identity/role/
  organization mapping; use a supported server-only provider operation and an
  approved recipient-bound, expiring, one-use activation channel; let the user set
  their own password; validate CRM linkage, seat admission and auditability in
  isolation before any production provisioning. No shared/operator-chosen customer
  credentials, manually asserted verification, public signup or raw SQL bypass.
  Until such a procedure is approved and verified, defer new users.
- With `BUSINESS_REGISTRATION_ENABLED=false`, `/auth/onboarding` is denied. Its
  existing creation flow creates an owner membership; platform administration
  currently approves existing organizations/Pilots and has no organization-create
  endpoint. Do not enable registration/email-readiness flags or invoke internal
  creation helpers as a shortcut. A reviewed, explicitly approved existing
  organization/owner/membership provisioning plan is a private-launch prerequisite.
- Forgot-password and invitation UI/API remain present and can attempt provider
  email; SMTP deferral does not technically disable those endpoints. Do not invoke
  them or promise delivery. Approve the restricted cohort's lockout/support policy
  and how access to email-triggering actions is controlled before launch. No
  automated invitation service is introduced or enabled. Lost-password users wait
  for approved recovery; no administrator password reset or verification bypass.

### Exact proposed production Auth change — NOT executed

Target existing project `hazrihbiqsflnmlcycen`, after recovery readiness and separate
Auth execution/window approval. Re-read current configuration and capture a
non-secret baseline immediately before applying this Management API delta:

```json
{
  "site_url": "https://b2-b-crm.vercel.app",
  "uri_allow_list": "https://b2-b-crm.vercel.app/login",
  "disable_signup": true,
  "mailer_autoconfirm": false,
  "external_email_enabled": true
}
```

Use authenticated `PATCH /v1/projects/hazrihbiqsflnmlcycen/config/auth`; credentials
stay outside chat/logs/Git. Retain anonymous sign-in OFF, existing identity UUIDs,
passwords, sessions and signing keys; configure no SMTP/unverified sender. The
last live check found signup ON, confirmation ON and email login ON; URL baseline
was localhost/empty at the earlier dashboard inspection and must be reread.
Disabling public signup preserves existing-user sign-in and server-authorized
admin creation; admin provisioning still needs separate identity/security approval.
Read back settings and verify approved existing-user login/session/logout and
rejected public registration after execution. No signup probe or email now.
Do not automatically restore unsafe public-signup settings on failure: stop and
request exact recovery/rollback authorization while protecting production data.

### Release checklist by scope

| Scope | Required gates / status |
| --- | --- |
| Private existing-user Pilot | Green CI on final commit; provider and application public signup OFF; confirmed linked approved cohort and verified production platform administrator; explicit organization/owner/membership mapping/provisioning; tenant enforcement and real production Pilot plan ID; 30 days/five seats including owner/all four entitlements; platform-only activation/renewal; expiry and worker denial/data preservation; payment UI/checkout/webhooks OFF. Existing hosted/security evidence retained; actual production cohort/access unverified. |
| Mandatory for every production launch | Approved legacy mapping and preservation; full Auth/private Storage/PostgreSQL recovery destinations and restore verification; independent key custody/version retention, retention period, RPO/RTO; validated production configuration; approved operator/window/write barrier/communications; fresh encrypted cutover backup and isolated PG17 rehearsal; separate Auth, export, privilege, migration, merge and deployment approvals. ALL remain release gates. |
| Deferred private-Pilot functionality | New identities/memberships via invitations, independent second staging inbox and live invitation/seat-acceptance delivery tests, email confirmation delivery and lost-password recovery. Resend sender/domain/DNS/TLS/credentials and exact recipients remain unapproved; no unverified sender. Approve explicit unavailable-service/support restrictions for the existing-user cohort. |
| Future public registration | A new explicit business approval to open registration; verified sender/domain and operational SMTP; confirmation/recovery/invitation delivery and abuse/rate-limit checks; tested identity/CRM onboarding, ownership, isolation and seat admission; reviewed registration/email-readiness flags and provider settings. Organization/Pilot approval remains platform-only; payments remain OFF unless independently authorized later. |

Pilot code/security behavior is unchanged: activation requires an existing active
verified owner, counts seats, sets 30 days using server time and audits approval;
stale renewal retries cannot extend again. Tenant and expired-worker boundaries,
private Storage and cross-tenant denial retain prior hosted/isolated evidence.
Production billing is rejected before provider calls; no Lemon Squeezy credentials
or webhook activation needed. Scheduled reminders stay OFF. Prior 12/12 CI was
for `8d4f91a`; documentation-commit CI must be checked again after push.

**Next approvals:** nominate exact existing administrator/cohort and approve
snapshot-specific mappings/provisioning plus restricted support/email-action
policy; approve complete recovery scope/destinations, custodians/retention/RPO/RTO
and rehearsal; then separately approve the exact Auth delta and cutover actions.
Merge and production deployment are separate approvals; main-branch automatic
deployment must be controlled before any merge. PR #1 stays Draft. No new phase.

Sources: [signup and confirmation configuration](https://supabase.com/docs/guides/auth/general-configuration),
[password login and email-dependent recovery](https://supabase.com/docs/guides/auth/passwords),
[server-only admin creation](https://supabase.com/docs/reference/javascript/auth-admin-createuser),
[provider admin implementation](https://github.com/supabase/auth/blob/master/internal/api/admin.go).
