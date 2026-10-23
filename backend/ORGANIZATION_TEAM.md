# Phase 3

`/team/members` and `/team/invitations` use the selected, verified organization.
Owners can manage owner permissions; administrators cannot. Organization-row
locking serializes access changes and preserves the final active owner. Existing
user-management routes use the same safeguards. Global account roles are unchanged.

Invitations expire after seven days and grant no access until the verified email
recipient accepts via `/auth/invitations/{id}/accept`. Supabase sends invitation
links for new identities and sign-in links for existing identities. Existing
email templates must deliver token hashes to the configured `/login` callback;
live email delivery/template verification remains pending an approved test recipient.
No provider keys or Auth IDs are returned in team invitation responses.

Removal is non-destructive: retain membership/ownership history, mark access
inactive and set `removed_at`. Revoke sessions selected into that organization;
sessions in other organizations remain valid. Membership checks deny access from
unselected sessions and legacy development tokens as well. A new invitation and
recipient acceptance are required to restore a removed membership.

Migration `a1b2c3d4e503` adds invitation records with default-deny RLS and removal
metadata. It assigns no owners and changes no legacy business data. Production
tenant activation stays disabled. Run `scripts/tenant_foundation_qa.py --team`
and `--isolation` separately; both create disposable local PostgreSQL clusters.
