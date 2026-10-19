# Phase 7A.3 release gate — 2026-10-18

**Current launch decision (2026-10-19): payment-free, manually approved access.**
Lemon Squeezy is postponed and preserved. Its credentials and live sandbox tests
are no longer prerequisites for this launch. Keep `LEMON_SQUEEZY_TEST_ENABLED`
false; production billing is additionally refused by the adapter. Historical
billing blockers below describe the earlier paid-launch plan; the Phase 7A.8
go/no-go checklist at the end supersedes them.

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
