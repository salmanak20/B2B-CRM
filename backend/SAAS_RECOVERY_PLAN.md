# SaaS recovery plan — approval required

Planning only. No production restore, migration, configuration change or release
is authorized by this document. Phase 7A.5 approval covered one public-only backup
and disposable local rehearsal; it did not cover Auth/Storage export or key escrow.

## Recovery set and approvals

| Component | Required recovery material | Approval / validation |
| --- | --- | --- |
| PostgreSQL | Consistent encrypted public dump, revision, extension versions, schema/constraints, baseline IDs/counts/content fingerprints and grants | Approved source/destination, capture window and operator; restore into isolated PG17 and compare before/after migrations |
| Supabase Auth | Existing users/identity UUIDs, identities and password hashes through a provider-supported export; provider settings, confirmation/signup flags, redirect/site URLs, MFA/session configuration and SMTP/OAuth configuration | Separate sensitive export/restore approval; preserve UUIDs and account links; no signup API, new identities or notification emails during recovery |
| Private Storage | Object bytes plus paths/checksums, bucket configuration, object metadata/ownership, policies/grants and public attachment rows | Separate encrypted object/metadata capture approval; preserve keys/IDs; compare counts/checksums and enforce private access |
| Keys | Original backup decryption material, app session-encryption key versions, provider key references and separately secured API/SMTP credentials | User-selected independent secure vault/location, custodians, retention/deletion period and restore verification; never commit keys or put them beside the archive |

Database dumps alone do not recover Storage object bytes. Public-only dumps also
omit managed Auth/Storage metadata. Use the provider-supported recovery method for
the approved destination/version; do not blindly replay managed Auth DDL over an
existing project. If existing identity UUIDs cannot be preserved, stop for an
explicit reviewed reconciliation. Do not create replacement customer accounts.

Supabase-managed signing private keys must not be assumed exportable. Record the
key IDs/project/issuer and an approved provider recovery or rotation procedure.
Restored sessions may be invalid with another issuer/key; plan verified re-login,
not automatic session resurrection. Preserve the original app encryption key for
encrypted stored tokens and the original Fernet decryption material for each
archive. Verify escrow can decrypt before rotating/deleting the old key. The
current ACL-restricted local archive remains only one recovery copy; independent
key retention and recovery-set storage are still unconfirmed. Retention, RPO and
RTO require the user's decisions; no paid resource or deletion policy is assumed.

## Capture and account mapping

1. Obtain separate production release/write-barrier approval. Before migration,
   take a **new approved** consistent encrypted backup after controlling customer
   writes; coordinate Auth/Storage capture to the same recovery boundary. Record
   timestamps, revisions, checksums and any unavoidable cross-service gap. The
   October 18 rehearsal proves the procedure, not freshness at future cutover.
2. Prepare the legacy manifest against that exact snapshot. Explicitly map each
   existing CRM user ID, existing Auth UUID/link state, organization membership,
   role and record assignment. Preserve IDs, roles, timestamps, relationships and
   unlinked historical accounts. Do not promote any Legacy owner or infer an Auth
   identity from an email. Keep the approved Legacy owner pending unless an
   existing verified identity is separately approved.
3. Review shared pipelines/stages/settings/workflows, audit actors, notifications,
   attachments and orphan/polymorphic references. Stop on ambiguous/unmapped rows
   or a changed baseline; do not clone/delete history or silently assign it.
4. Rehearse on isolated PG17 with outgoing Auth/email/billing calls disabled and
   no public app access. Customer data must not be mixed with synthetic hosted
   staging or sent to external testing services. Auth/Storage recovery needs its
   own approved isolated destination, provider method and exposure controls.

## Acceptance and rollback boundary

- Match restored schema/required extensions, original IDs, content fingerprints,
  row counts and all FK/tenant relationships. After approved mapping, reconcile
  all tenant-owned rows, ownership/assignees, singleton/shared configuration and
  private-object references. Nullable columns are not evidence mapping is complete.
- Verify preserved Auth UUID links, explicit membership roles, no new owner/global
  privilege, two-organization isolation, revoked/suspended access, and private
  upload/download/expiry. Use only approved delivery inboxes. Reconcile any future
  billing bindings with the provider before entitlement activation; no paid state
  may be inferred from a redirect or stale recovery snapshot.
- Decide application rollback versus forward database repair with the approved
  write barrier. Keep compatible additive schema when rolling code back. Existing
  populated SaaS downgrade guards deliberately refuse data loss; do not bypass
  them. Restoring an older snapshot can lose later customer writes and identities:
  require explicit recovery-point/data-loss approval and reconcile those writes.
- Rehearse recovery into a separate destination first. Never overwrite production,
  delete Storage objects or rotate signing/encryption keys as a shortcut. Release
  remains NO-GO until the complete recovery set, mappings, external tests and
  separately authorized production configuration/release gates are signed off.

Provider references: [database backups](https://supabase.com/docs/guides/platform/backups),
[supported platform restore considerations](https://supabase.com/docs/guides/self-hosting/restore-from-platform).
