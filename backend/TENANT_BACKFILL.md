# Phase 1A legacy-data backfill plan

Status: schema foundation only. Revision `a1b2c3d4e501` follows `f8b3015a0001`.
The migration inserts no organizations, memberships, roles, owners, or business rows.
Existing IDs, ownership, global users, `User.role_id`, routes and authentication stay intact.
All 15 tenant-owned tables receive nullable `organization_id` without defaults.
No production migration or backfill is authorized by this phase.

## Decisions required before any backfill

- An accountable data steward must approve organization identities, names/slugs and
  the organization assignment of each existing record. Do not infer an organization
  owner from the first user, global admin role, record owner, email domain or login.
- Approve memberships and organization roles independently from record ownership.
  One global user can join multiple organizations with different roles. Select
  owners explicitly; zero or multiple owners remain possible in this foundation.
- Membership roles are `owner`, `admin`, `sales_manager`, `sales_rep`, `viewer`.
  `permission_role_name` references existing `roles.name`; owner maps to admin,
  every other role maps to its namesake, enforced with a check constraint. The ORM
  insert default supplies that mapping; explicit SQL and role updates must set both
  fields. No role definitions or permissions are inserted or changed by migration.
- Decide whether existing pipelines/stages, singleton settings ID 1 and workflow
  rules/runs belong to one organization or require reviewed splitting/duplication.
  Splitting shared parents cannot preserve every original relationship unchanged;
  resolve those conflicts explicitly rather than guessing or silently cloning.
- Map notification events, audit history, notifications and attachments, including
  user-only or polymorphic entity references with ambiguous organization identity.
  Preserve attachment storage paths until a separately reviewed storage plan.

## Future execution protocol (not executed or enabled in Phase 1A)

1. Confirm the target database/environment and its revision. Take an encrypted
   backup via the existing `app.db.safe_migrate` tooling only under separate
   authorization; retain the encryption secret and prove restore in an isolated
   database. Its archive-list check alone is not a restore rehearsal. Back up
   managed Auth/Storage separately. Record baseline IDs, row counts and content
   fingerprints for every affected table.
2. Export a read-only inventory and prepare a versioned, approved manifest with
   organization definitions, `(user_id, organization, role)` memberships and
   explicit `(table, existing_id, organization)` assignments. Record approver,
   source revision, baseline fingerprint and unresolved rows. Stop on unknown IDs,
   duplicate assignments, missing members, orphaned links or conflicting tenants.
3. Validate the full relationship graph before writing. Every company/contact/
   lead/deal/pipeline/stage/task/activity/workflow/event edge must stay in one
   organization. Owners, assignees, actors, recipients and uploaders must have a
   membership in that organization. Review historical/inactive users separately;
   membership FK existence does not grant active access.
4. Rehearse migration and the reviewed manifest on a restored, isolated PostgreSQL
   database. Verify checksums and counts, unchanged IDs/ownership, no unresolved
   assignments, organization-scoped uniqueness and foreign-key integrity. Include
   polymorphic references and membership-role mappings in validation.
5. Before a future production backfill, freeze legacy writes or use an explicitly
   reviewed write barrier: current routes continue inserting NULL tenant keys.
   Lock affected records, verify the baseline again, create only approved
   organizations/memberships and update explicit IDs in coordinated transactions.
   Deferred composite FKs permit linked rows to be assigned in one transaction;
   `SET CONSTRAINTS ALL IMMEDIATE` validates the completed graph before commit.
   A resumable process must reject conflicting existing assignments, log exact
   changes and remain idempotent. No executable backfill is supplied in Phase 1A.
6. Reconcile counts, IDs, fingerprints, all NULL tenant keys, every relationship
   and the approved manifest. Keep columns nullable until reconciliation is signed
   off. NOT NULL enforcement belongs to a later separately reviewed migration.
   Rollback after assignment requires a reviewed recovery plan: this migration's
   downgrade refuses to discard any organization or membership rows.

## Constraint boundaries and Phase 2 prerequisites

- Composite `(organization_id, related_id)` foreign keys enforce same-tenant links
  for populated keys and reference membership `(organization_id, user_id)` for
  tenant-owned user references. They are deferred to transaction commit. Existing
  single-column FKs and delete behavior remain. Partially assigned graphs must
  be reconciled: a NULL child tenant key bypasses a composite FK by SQL semantics.
- Generic `(entity, entity_id)` links in attachments, notifications and audit logs
  cannot have ordinary foreign keys to multiple target tables. Validate against
  the approved manifest; tenant-aware authorization/validation is still required.
- Settings are unique per non-NULL organization. Pipeline names are unique per
  organization; a partial unique index retains uniqueness among legacy NULL rows.
  Stage ordering/names remain unique per pipeline; workflow rule/lead pairs and
  global attachment paths retain their existing stronger uniqueness constraints.
- Users, global permission/role definitions, auth sessions and rate buckets remain
  global. Audit logs and notification events are included in tenant metadata.
- RLS/default-deny Data API access is enabled for organizations/memberships, matching
  the prior migration; no browser policies or grants are added. The existing
  backend bypasses RLS. No organization endpoints, selector, routing, membership
  authorization, invitations or multi-tenant access are activated. Do not expose
  tenant features or treat this foundation as isolation of the running API.

## Isolated verification

`backend/.venv/Scripts/python.exe scripts/tenant_foundation_qa.py` from the repo root
creates a fresh localhost PostgreSQL cluster and runs the focused model/migration
suite plus legacy authentication regression tests. It never reads the
production database URL; all subprocess connection settings are explicitly local.
PostgreSQL binaries default to `C:/Program Files/PostgreSQL/18/bin` and can be set
with `CRM_TEST_PG_BIN`. The temporary cluster is stopped and removed on exit.
