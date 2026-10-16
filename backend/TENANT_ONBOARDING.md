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

The server validates provider email confirmation before workspace creation.
Send a stable UUID `request_key` to `POST /auth/onboarding`; retries reuse the
receipt, while changed details conflict. Fresh explicit requests can create
additional workspaces. Removed memberships cannot be restored by retrying.
New workspaces contain only owner membership and essential workspace settings.

Focused verification: `python scripts/tenant_foundation_qa.py --onboarding`,
then separate `--isolation` and `--team` runs; frontend Playwright onboarding/team
tests, `npm run build`, and `npm run check`. Auth calls in these tests are mocked.
