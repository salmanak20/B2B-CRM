# CRM Pro release and operations

## Current release state — 15 October 2026

The source implementation is in this workspace. Supabase project `hazrihbiqsflnmlcycen` is the existing active `b2b-crm` database. Migration `f8b3015a0001` was applied after an encrypted backup. Existing business-table counts were unchanged. Anonymous REST requests to users/companies changed from HTTP 200 to 401. The trusted FastAPI backend retains access.

The updated app has **not** been deployed to Vercel. Project `b2-b-crm` (`prj_qpzgCm1EHryhz6kfC0TB5K45NTYR`) belongs to scope `salman-yousafzais-projects` (`team_e30J2LJIMChxGCUI4MtIiwEK`). The connector lists it but opening it returns HTTP 403. CLI fallback found no authenticated credentials. Grant that scope to the connector or authenticate the CLI to this same scope; do not create another project.

`salmanyousafzai736@gmail.com` was absent from both CRM profiles and Supabase Auth. No administrator password was invented, no invitation was sent, and no business/test records were inserted into production. The missing `SUPABASE_SERVICE_ROLE_KEY` prevents administrator invitation and private-storage configuration. Supply it through ignored local environment variables and the deployment dashboard, never chat or frontend variables.

## Architecture and tenancy

The existing Vite HTML/ES-module frontend and FastAPI/SQLAlchemy/Alembic backend are preserved. PostgreSQL stores CRM records; Supabase Auth handles production identities; Supabase Storage holds private attachments. The root `vercel.json` uses Vercel Services (currently Beta) to serve frontend and API on the same origin. Set the Vercel project root to this repository root, and Node.js to 22 or 24. Upload/build the current workspace, including untracked implementation files; deploying the old Git commit will omit these changes.

This remains one workspace per deployment. Administrators/managers manage workspace records, representatives work on owned records and assigned tasks, and viewers have workspace read-only access. There is no multi-organization selector or unsupported tenant-sharing feature. Separate organization databases/deployments are required until an explicit tenant migration is implemented. Notes use activity records of type `note`; workspace settings use one persisted record; currency is USD for consistent totals.

Vercel Services documentation: <https://vercel.com/docs/services> and routing reference: <https://vercel.com/docs/services/routing>. Configuration was detected by Vercel CLI locally. Full Vercel runtime verification remains pending; the local CLI encountered a Windows quoting problem with a uv executable under a path containing spaces. This is a local CLI issue, not evidence of a successful hosted build.

## Server environment

Use `backend/.env.example` as the complete template. Required production values:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Existing Supabase PostgreSQL connection with TLS; use its session pooler, or a correctly configured transaction pooler |
| `JWT_SECRET_KEY` | At least 32 random characters for encrypted server sessions; preserve this in a secret manager |
| `AUTH_PROVIDER` | `supabase` |
| `SUPABASE_URL` | `https://hazrihbiqsflnmlcycen.supabase.co` |
| `SUPABASE_PUBLISHABLE_KEY` | An enabled public/publishable or legacy anon key for that project |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only privileged key for invitations and private storage |
| `SUPABASE_STORAGE_BUCKET` | `crm-attachments` |
| `FRONTEND_URL` | `https://b2-b-crm.vercel.app` |
| `CORS_ORIGINS` | `["https://b2-b-crm.vercel.app"]`; add only explicit HTTPS preview origins when needed |
| `ENVIRONMENT`, `DEBUG` | `production`, `false` |
| `COOKIE_SECURE`, `ALLOW_SELF_REGISTRATION` | `true`, `false` |
| `SESSION_HOURS`, `REMEMBER_DAYS` | `8`, `30` |
| `DUE_NOTIFICATIONS_ENABLED` | `false` on serverless; notification fetch delivers due events once |

Do not prefix server secrets with `VITE_`. The browser always calls `/api/v1`. Local Vite development uses `API_BACKEND_ORIGIN=http://127.0.0.1:8000`. Runtime settings reject legacy production auth, insecure cookies, HTTP frontend origins, wildcard/non-HTTPS CORS and non-PostgreSQL production databases.

Install runtime packages with `pip install -r backend/requirements.txt`; development checks use `backend/requirements-dev.txt`. Both runtime and frontend dependencies are pinned or locked. Changing the session encryption secret invalidates encrypted provider sessions; plan a sign-in transition and preserve the old secret for encrypted backup recovery.

## Supabase Auth and administrator setup

1. In Supabase Auth URL configuration, set Site URL to `https://b2-b-crm.vercel.app` and allow `https://b2-b-crm.vercel.app/login`. For previews, explicitly allow the chosen preview login URL.
2. Configure reliable SMTP/email delivery, email verification and a minimum password length of 12. The app enforces 12 characters and a 72 UTF-8 byte maximum on password creation/change; the provider remains authoritative.
3. Configure **Recovery** email links to the following token-hash route so tokens can be exchanged on the server without storing browser bearer tokens:

   `{{ .SiteURL }}/login?token_hash={{ .TokenHash }}&type=recovery`

   Configure **Invite** links as:

   `{{ .SiteURL }}/login?token_hash={{ .TokenHash }}&type=invite`

   Provider dashboard templates and real inbox delivery are not accessible through the available connection and remain unverified. The standard implicit-token redirect template is incompatible with this server-session flow until replaced.
4. With the server environment configured, run from `backend`:

   ```powershell
   .\.venv\Scripts\python.exe -m app.db.bootstrap_admin --email salmanyousafzai736@gmail.com --check
   .\.venv\Scripts\python.exe -m app.db.bootstrap_admin --email salmanyousafzai736@gmail.com --invite
   ```

   The second command sends the requested account invitation through Supabase and creates/links its administrator CRM profile. The user chooses their password through the emailed link. Do not run it with local legacy auth selected. For an existing verified Supabase identity, use `--auth-user-id UUID` instead of `--invite`; the tool checks its email and verification state.
5. After signing in, use User Management to invite real colleagues. Existing legacy CRM profiles can use **Set up sign-in**, preserving their profile IDs, roles and customer ownership. If the email already has a verified Auth account, supply that Auth UUID through this form. Do not delete and recreate legacy users.

Normal browser sessions last up to eight hours with a nonpersistent HttpOnly cookie. Remember Me permits up to 30 days. Browser session restore behavior is browser-dependent; absolute server expiry still applies. Provider access/refresh tokens are encrypted in the database. Logout revokes the server session. Password changes require current-password verification or a verified recovery session and revoke all local sessions. Deactivation revokes local sessions immediately. SSO is absent until a real provider is configured.

## Private attachments

Create the **private** `crm-attachments` Storage bucket in the same Supabase project, with a 3 MB upload limit and supported content types PDF, PNG, JPEG, TXT and CSV. Do not grant public access or browser Storage policies. The trusted backend verifies record access, file size/type/content, and requests 60-second download links. A metadata row stores the related CRM entity, uploader and object path. Parent deletion is blocked until attachments are removed.

Live Storage upload/download has not been verified because privileged Storage access is not configured. The UI accurately disables uploads and explains this condition. Automated contract tests cover validation, signing expiry and access isolation without claiming a real cloud upload.

## Migration, backup and rollback

`backend/alembic/versions/f8b3015a0001_sessions_workspace.py` is additive: identity/preferences fields, actual deal closing timestamps, sessions, persistent rate limits, workflow rules/runs, settings, notification deduplication and attachment metadata. No fictional CRM data or default sales pipeline is seeded. An administrator creates their own pipeline and stages. Existing IDs/ownership are preserved. Historical won deals retain an unknown close date rather than inventing one.

RLS is enabled on all 22 application/migration tables and all table privileges are revoked from `anon` and `authenticated`. This is intentional default-deny browser access. FastAPI connects as a trusted table owner/BYPASSRLS role and enforces the tested role/ownership rules. Supabase's informational “RLS Enabled No Policy” finding is expected for this architecture: <https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy>. Do not add broad browser policies to silence it. The earlier critical RLS-disabled issue is documented at <https://supabase.com/docs/guides/database/database-linter?lint=0013_rls_disabled_in_public>.

For subsequent releases, from `backend`:

```powershell
.\.venv\Scripts\python.exe -m app.db.safe_migrate --backup-only
.\.venv\Scripts\python.exe -m app.db.safe_migrate --apply
```

The tool encrypts a custom-format public-schema dump in ignored `backend/.backups`, verifies it with `pg_restore --list`, records original revision/counts and checks unchanged existing-table counts after upgrading. This is archive-list verification, not a full production restore rehearsal. Preserve the backup and its original `JWT_SECRET_KEY` in protected storage. Supabase-managed Auth/Storage have separate provider backup requirements.

Prefer rolling application code back while retaining additive schema columns/tables. Never run a production downgrade after new records/sessions/attachments exist: dropping the new tables loses those features' data. The full downgrade/reapply test is for an isolated empty database only. To recover from a destructive database incident, decrypt the chosen backup with its original session secret and use `pg_restore` into a separate database for review; coordinate business writes before any production restore. RLS must remain enabled even if old code is restored.

## Verification and release order

1. Resolve the exact Vercel scope error and privileged Supabase environment/configuration.
2. Review the local QA report and current source. Database migration/protection is already applied; do not re-seed business data.
3. Link the existing Vercel project to the repository root and deploy a protected preview of **this workspace**. Ensure preview URL, cookie/origin and Auth redirects match its configuration.
4. Verify `/api/v1/health`, `/api/v1/health/ready`, unauthenticated 401s, every clean route and original `/.../code`/`.html` entry URL, static assets, CSP and secure cookies. Verify actual provider invitation, email verification, recovery, password change, refresh, logout and private attachment upload/download with an approved staging account/database. Do not run automated fixture tests against production.
5. Promote the verified build to `https://b2-b-crm.vercel.app` and repeat read-only health/auth checks. Retain the prior deployment ID for rollback.

Local tests: `python -m pytest -q` from backend uses isolated SQLite. `python scripts/postgres_qa.py` from the repository root using the backend virtualenv creates a private disposable localhost PostgreSQL 18 cluster with a random password, tests fresh migration/downgrade/reapply and runs the suite. Playwright (`npx playwright test` in the frontend) launches its own isolated API/SQLite database, generates a random fixture password, and tests Chromium, Firefox, WebKit and mobile Chromium. Fixture servers explicitly require `CRM_TEST_RUN=1`; generated test credentials are never production credentials.

Date counts use record creation dates. Won revenue uses recorded closing timestamps; historical unknown closes are included only in the all-time “Unknown close date” bucket. Date filters use inclusive UTC days; personal timestamp display follows the saved timezone. Due reminders are generated on notification fetch on Vercel, and optionally by a 60-second worker on a long-running host. Arbitrary scheduled email campaigns, weekly digest delivery, multitenancy, SSO and multiple currencies are not implemented features.
