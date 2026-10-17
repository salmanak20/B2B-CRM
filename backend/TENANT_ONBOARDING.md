# Business onboarding

Migration `a1b2c3d4e504` adds private signup intents and provisioning receipts;
it does not modify existing CRM rows or Legacy Organization ownership.

Registration defaults off (`BUSINESS_REGISTRATION_ENABLED=false`). Local/staging
verification requires Supabase Auth and `TENANT_ISOLATION_ENABLED=true`.
Production additionally requires `AUTH_EMAIL_CONFIGURATION_VERIFIED=true`;
leave both registration flags false until live delivery and redirects pass review.

Provider setup pending: enable Confirm Email, configure SMTP and allowed
`FRONTEND_URL/login` redirect, and set the confirmation template to the login URL
with `?token_hash={{ .TokenHash }}&type=signup`. Verify delivery, expiry and redirect
with approved test accounts before requesting production activation. No deployment
or production feature activation is part of this phase.

Free staging may use Supabase's built-in mailer with explicitly approved team
inboxes (currently two messages/hour); custom SMTP stays disabled. Default signup
links verify email, then the user signs in with the password chosen at signup.
Recovery uses PKCE with an encrypted, HttpOnly, one-hour browser cookie and a
one-use provider code. Request the latest email through Forgot password and open
it in the same browser/profile; Sign In does not create or change passwords.
Old implicit recovery links must be replaced. A `token_hash` template remains
supported, including for invitations; live invitations need a second approved
inbox. Do not equate delivered email with a successful password-reset flow.

The server validates provider email confirmation before workspace creation.
Send a stable UUID `request_key` to `POST /auth/onboarding`; retries reuse the
receipt, while changed details conflict. Fresh explicit requests can create
additional workspaces. Removed memberships cannot be restored by retrying.
New workspaces contain only owner membership and essential workspace settings.

Focused verification: `python scripts/tenant_foundation_qa.py --onboarding`,
then separate `--isolation` and `--team` runs; frontend Playwright onboarding/team
tests, `npm run build`, and `npm run check`. Auth calls in these tests are mocked.
