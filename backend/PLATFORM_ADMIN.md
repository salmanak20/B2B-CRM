# Platform administration

Migration `a1b2c3d4e505` adds private platform permissions/audit tables and a
non-destructive suspension flag. No account is promoted by migrations or startup.

The first administrator must be an explicitly selected existing active user with
a matching, email-confirmed Supabase identity. No Legacy owner is inferred.
For isolated local staging only, set `PLATFORM_BOOTSTRAP_DATABASE_URL` securely,
configure the server-side staging Supabase provider, then run from backend:

`python -m app.platform_bootstrap --user-id VERIFIED_ID --email VERIFIED_EMAIL --auth-user-id VERIFIED_AUTH_UUID`

This operator-only process refuses unapproved targets and closes after
the first grant. Production provisioning is intentionally not executed or enabled
here. Further grants/revocations require a verified active platform administrator
through `/platform-admin`; the final active administrator cannot be revoked.

For an explicitly approved dedicated hosted staging project, additionally pass
`--hosted-staging-project-ref APPROVED_REF`, set `ENVIRONMENT=staging`, and use
matching staging Auth and database credentials. The command checks both project
identities, uses direct/Session pooler port 5432 with TLS, and rejects connection
query overrides. Production mode is always refused. This
does not enable production bootstrap or grant any organization membership.

Platform access does not create organization memberships or bypass tenant guards.
Suspension invalidates selected organization sessions, hides suspended choices,
blocks tenant operations/background delivery, and retains all CRM rows. Reactivate
then sign in/select the organization again. Audit events contain platform actions
only; tenant audits, leads, contacts, deals and files are not exposed.

## Administrator authentication and provisioning review — 23 October 2026

`/platform-admin/login` uses the existing Supabase password login and encrypted
server cookies, followed by TOTP enrollment/challenge. Every platform operation
requires the bound active platform identity, a provider-validated token at AAL2,
and an existing verified factor. Production configuration refuses disabled MFA.
Enrollment includes a private QR code and manual key. A user-requested restart
replaces only their unverified TOTP factors using their own provider token;
verified factors cannot be removed through this flow.
No token is returned to browser storage. Password changes and all-session
revocation are available from Platform Settings. Login/enrollment/verification and
session revocation use existing rate-limit, session and platform-audit services.
Documented provider errors distinguish incorrect credentials, ended sessions,
incorrect authenticator codes and expired challenges. Raw provider messages and
credentials are never echoed to the browser.

Production provisioning remains **blocked**, independently of deployment status:

- Independently establish the nominated person's identity and mailbox control.
  An email address is not a privilege predicate. Confirm exact Auth UUID and
  proposed CRM profile/membership mapping; preserve existing ownership.
- Satisfy the documented schema/recovery/configuration prerequisites first.
  Obtain a specific identity-creation approval naming the person, environment,
  verified delivery channel and activation window. With SMTP unavailable, new
  identities wait; no manually asserted confirmation or temporary shared password.
- The recipient chooses a unique password through the approved private provider
  activation form. Do not put a password or activation token in chat, Git, operator
  arguments or reports. Validate sign-in, confirmation and recovery separately.
- Obtain a separate CRM linkage approval for the exact existing/new profile ID and
  Auth UUID. Validate the provider identity using `verify_target`; never infer a
  link or organization from email alone.
- Obtain a separate initial platform-grant approval and reviewed execution plan.
  Reuse the existing administration lock, closed-bootstrap check, verified target
  binding and transactional platform audit. **The existing bootstrap deliberately
  refuses production. This procedure does not authorize removing that guard or
  inserting a privilege row by SQL.** Review the controlled production execution
  mechanism only after prerequisites/approvals; its execution is a release gate.
- Have the recipient enroll TOTP privately. Verify AAL1 denial, AAL2 admission,
  ordinary-owner denial, password change, logout and all-session revocation. Do
  not mark provisioning complete before those checks pass.

No production identity, linkage or privilege was created by this development work.

## Usage, limits and manually registered businesses

Migrations `a1b2c3d4e508` and `a1b2c3d4e509` add private current totals, prospective daily aggregates,
per-access-period workflow counters and optional subscription resource limits.
It records no customer CRM contents and fabricates no historic events. API request
counts are explicitly unavailable. PostgreSQL triggers serialize allocation using
an organization `FOR NO KEY UPDATE` lock, compatible with FK key-share locks.
Failed writes roll counters back. Attachment quota is reserved before upload;
confirmed Storage cleanup releases the reservation. Ambiguous upload/cleanup
failures retain a durable pending attachment and its quota until cleanup succeeds;
pending downloads are denied and owners can retry deletion. Deleting a workflow run never
refunds an execution. Renewal starts a new access period.

New Pilots use the user-approved defaults: 5 seats including owner, 500 leads,
500 contacts, 250 companies, 500 deals, 1,000 tasks, 1 GiB attachment bytes, and
1,000 workflow executions per access period. Existing subscriptions are not
rewritten by migration. Existing Pilots with missing resource limits require an
explicit quota review before additional metered allocation; there is no unlimited
fallback. Their original seats/records remain preserved. Overrides are finite,
audited and protected against stale updates. Decreases never delete records.

The platform can register a suspended business with an existing provider-verified
owner and idempotent provisioning receipt, or explicitly assign a verified existing
owner. No Auth identity or global role is created. New businesses need separate
Pilot approval and reactivation before workspace access. Existing organizations
and owners are never automatically adopted or remapped.

With delivery readiness false, new-email invitations remain pending without an
Auth identity or provider call. Existing confirmed linked recipients can view and
accept their exact invitation after authenticated sign-in; seat admission and
revocation checks still apply. Recovery requests return an explicit unavailable
state until verified email delivery is enabled. This is not recovery readiness.
