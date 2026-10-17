# Phase 2

Tenant access is disabled by default (`TENANT_ISOLATION_ENABLED=false`). This is
a deployment gate, not a fallback to unscoped access: CRM requests return 503.
No production migration or activation has been performed.

Isolated staging requires approved Phase 1B mappings and Alembic revision
`a1b2c3d4e502`, which adds a nullable active organization to server sessions.
Set `TENANT_ISOLATION_ENABLED=true` only in the verified test/staging environment.
Existing tenant columns remain nullable; unassigned rows are inaccessible.

One active membership is selected automatically. With several memberships, use
`GET /api/v1/auth/organizations` and `POST /api/v1/auth/organization` with
`{"organization_id": ...}` in the authenticated cookie session. The optional
`X-Organization-ID` request header also requires a current active membership.
Memberships and organization permissions are checked on each request. Account
login/recovery and organization selection remain authentication bootstrap paths.

The application session scopes ORM reads, aliases, joins, aggregates and bulk
deletes, validates ORM writes, and rejects raw/Core tenant SQL. Offline migration
and backfill tooling uses separate explicit connections. Background reminders
use a separate scoped session per organization. Private file downloads recheck
membership through the backend; storage paths already in use are preserved.

Focused verification: `backend/.venv/Scripts/python.exe scripts/tenant_foundation_qa.py --isolation`.
Fixtures and migrations run in a fresh disposable local PostgreSQL database.
