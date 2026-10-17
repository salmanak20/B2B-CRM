# Platform administration

Migration `a1b2c3d4e505` adds private platform permissions/audit tables and a
non-destructive suspension flag. No account is promoted by migrations or startup.

The first administrator must be an explicitly selected existing active user with
a matching, email-confirmed Supabase identity. No Legacy owner is inferred.
For isolated local staging only, set `PLATFORM_BOOTSTRAP_DATABASE_URL` securely,
configure the server-side staging Supabase provider, then run from backend:

`python -m app.platform_bootstrap --user-id VERIFIED_ID --email VERIFIED_EMAIL --auth-user-id VERIFIED_AUTH_UUID`

This operator-only process refuses non-local/non-staging targets and closes after
the first grant. Production provisioning is intentionally not executed or enabled
here. Further grants/revocations require a verified active platform administrator
through `/platform-admin`; the final active administrator cannot be revoked.

Platform access does not create organization memberships or bypass tenant guards.
Suspension invalidates selected organization sessions, hides suspended choices,
blocks tenant operations/background delivery, and retains all CRM rows. Reactivate
then sign in/select the organization again. Audit events contain platform actions
only; tenant audits, leads, contacts, deals and files are not exposed.
