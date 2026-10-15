"""Build the implementation QA artifact from completed test evidence."""
import html,json,shutil
from pathlib import Path
from datetime import datetime,timezone
from markdown_it import MarkdownIt

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'qa-results'/'implementation'
browser=json.loads((OUT/'browser-final-functional.json').read_text(encoding='utf-8'))
pg=json.loads((OUT/'postgres-verification.json').read_text(encoding='utf-8'))
perf=json.loads((OUT/'local-performance.json').read_text(encoding='utf-8'))
audit=json.loads((OUT/'python-dependency-audit.json').read_text(encoding='utf-8'))
initial=json.loads((ROOT/'qa-results/2026-10-15/defects.json').read_text(encoding='utf-8'))
status={
'QA-001':'Fixed locally: actual analytics contracts, close-based revenue and empty states; browser/API tests.',
'QA-002':'Fixed locally: create/edit uses actual pipeline/stage IDs; won/lost state and close time persist.',
'QA-003':'Fixed locally: stored company/contact IDs survive save and conversion.',
'QA-004':'Fixed locally: API DTOs include real company/contact/assignee names.',
'QA-005':'Fixed locally: profiles, related records, notes/history and attachment states use real APIs.',
'QA-006':'Fixed locally: server totals, sorting and working record pagination; >10-record regression test.',
'QA-007':'Fixed locally: persisted status/value rules create one task per rule/lead, with notifications.',
'QA-008':'Fixed locally: actual assignment/due events, read/delete/mark-all actions; no sample cards.',
'QA-009':'Development CRUD and production invitation integration implemented. Live invitations blocked by service-key/provider setup.',
'QA-010':'Fixed locally: profile/workspace updates persist; timezone affects displayed timestamps.',
'QA-011':'Fixed: formula-leading CSV cells are neutralized; exports retain real permitted records.',
'QA-012':'Fixed locally: 12-character/72-byte creation/change boundaries and safe validation errors. Provider password settings still need verification.',
'QA-013':'Fixed locally: profile/account changes, important CRM operations, imports and deletion emit audit events.',
'QA-014':'Automated regression passes: 13 routes per engine, serious/critical axe checks, dialog keyboard/focus. Manual assistive-technology certification not performed.',
'QA-015':'Fixed in tested widths: 50 route/viewport checks plus forms at 1440/1024/768/375/430.',
'QA-016':'Fixed: search includes owned OR assigned tasks and actual contact names.',
'QA-017':'Fixed locally: role-aware navigation/forms plus server permission/ownership checks; negative API/browser tests.',
'QA-018':'Fixed locally: Log Activity creates a real stored call/email/meeting/note/follow-up entry.',
'QA-019':'Fixed locally: trimmed nonempty names, finite numbers and valid date ranges are enforced.',
'QA-020':'Fixed at scan time: Vite upgraded, JWT/pip patched; npm and Python scans report zero known advisories.',
'QA-021':'Fixed: Vite creates dist output and shipped-asset scan passes. Hosted build blocked by Vercel access.',
'QA-022':'Fixed locally: calendar, automation and report routes load actual data and support navigation.',
'QA-023':'Fixed locally: company table headings and values match.'}
rows='\n'.join(f"| {x['id']} | {x['severity']} | {x['title']} | {status[x['id']]} |" for x in initial)
stats=browser['stats']
md=f'''# CRM Pro — implementation and QA report

**Date:** 15 October 2026 · **Workspace:** `S:\\Projects\\CRM`
**Release verdict: production sign-off blocked.** The implementation and isolated regression tests pass. Database protection is applied live. The updated app has not been published to Vercel, and real provider invitation/recovery and Storage remain unverified.

## What was delivered

The existing Vite page structure and FastAPI/SQLAlchemy/Alembic backend were extended. The indigo/Inter sidebar and card design are retained, with bundled fonts, responsive layouts and real forms. Shipped fictional CRM records, personalized login text, demonstration dashboard values, sample notifications and the static workflow builder were removed. Browser storage is no longer the source of CRM data or auth tokens.

Real operations now cover companies, contacts, leads/conversion, deals/pipelines/stages, tasks/calendar, activities/notes, notifications, workflow rules, profiles/workspace settings, user administration, CSV import/export and database-derived analytics. Supabase Auth, encrypted server sessions and private Storage adapters are implemented. Cloud-dependent controls expose an explicit configuration error/disabled state when unavailable.

## Test results

| Check | Result | Evidence and scope |
|---|---|---|
| Backend integration — SQLite | 99 passed | Fresh isolated in-memory test database; API validation, CRUD, relationships, role/owner isolation, sessions, imports, conversion, workflows, audits and provider contracts |
| Backend integration — PostgreSQL 18 | {pg['tests']} | Random-password localhost cluster; no production fixtures |
| Database migrations | Passed | Fresh upgrade, downgrade to base and reapply; offline SQL generation also verified |
| Functional browser regression | {stats['expected']} passed, {stats['unexpected']} failed, {stats['skipped']} skipped, {stats['flaky']} flaky | 29 scenarios across Chromium, Firefox, WebKit and mobile Chromium; three duplicate Chromium width sweeps intentionally skipped in other engines |
| Automated accessibility | Passed in four browser projects | 13 routes, WCAG 2/2.1 A/AA tags, no serious/critical axe findings; dialog focus/Escape and browser error checks |
| Responsive layout | Passed | 50 route/width combinations and dialog bounds at 1440, 1024, 768, 375, 430 pixels; actual horizontal tables may scroll inside their table container |
| Production frontend build | Passed | Vite dist generated; shipped assets scanned for known demo data, hardcoded login identity, mock tokens and runtime Tailwind CDN |
| Dependency scans | Zero known advisories | npm audit; Python pip-audit across {len(audit['dependencies'])} installed packages after patching JWT/pip |
| Local API availability | Passed | Health 200, DB readiness 200, unauthenticated auth/me 401 on restarted localhost:8000 |
| Live anonymous database access | Fixed and verified | users/companies HEAD returned 200 before migration and 401 afterward; all 22 public application/migration tables use RLS with direct anon/authenticated table grants revoked |
| Real Auth email and cloud Storage | Blocked | Integration code and isolated contract tests pass; no live email/Storage claim |
| Vercel hosted deployment | Blocked | Existing project is listed but access returns scope-specific 403; CLI has no credentials |

The first complete browser run exposed the shared badge accessible-name issue, Safari focus return and a sign-out redirect race. These were fixed and the complete functional suite rerun successfully. A later mobile task test exposed a test synchronization error: it filled an inert search field before the save dialog closed; the test now waits for dismissal while retaining its persistence assertions. Earlier failed-run JSON is retained alongside final evidence for traceability.

## Functional coverage

| Area | Verified behavior | Production qualification |
|---|---|---|
| Login/session | Required fields, password visibility, wrong-password feedback, dashboard redirects, session refresh/expiry, Remember Me, logout revocation, no browser token persistence | Browser regression uses development-only accounts in an isolated test API. Supabase login/recovery/password integration is contract-tested; real provider delivery/sign-in is pending |
| Accounts/access | Administrator create/deactivate, safe role controls, viewer mutation denial, representative owner/assignment scope, audit events, preserving existing user IDs when linking provider identities | No requested administrator exists yet; invitation needs configured privileged key |
| Companies/contacts | Create/edit/delete, linked company identity, detail/history/notes, safe dependent-record deletion, persistence after refresh/logout/login | Live business records preserved |
| Leads | Create/update/status/search/sort/page, stored relationships, idempotent company/contact/deal conversion, workflow triggers | No duplicate conversion on repeat requests |
| Deals/pipelines | User-created pipeline/stages, create/edit, stage movement, won/lost/open status, values, closing timestamp | Historical unknown close dates are not fabricated |
| Tasks/calendar | Assignment, status/completion, edit/delete, owner-or-assignee search, actual deadlines and month navigation | In-app due notifications are delivered on notification fetch on serverless, not by a guaranteed background scheduler |
| Notifications | Actual assignment/due rows, read/delete/mark all, due-event deduplication, unread badge | Current notification overview is bounded to 100 recent rows; no email-notification delivery claim |
| Workflows | Stored lead-status/minimum-value rule, enabled state, real assigned task + notification, one execution per rule/lead | Focused CRM automation; no arbitrary drag-and-drop workflow language or external campaign engine |
| Imports/exports | CSV selection, mapping/preview, per-row validation, duplicate skip/update, partial valid-row commit, error counts, ownership protection, CSV formula neutralization | UTF-8 CSV only; 2 MB/1000 rows per import; no spreadsheet workbook import |
| Analytics/reports | Real counts/amounts, empty/zero states, UTC range checks, closing-date revenue trend, team data, actual CSV records | USD workspace; record counts use creation date, won revenue uses actual closing date |
| Settings | Real profile/name, compact preference, display timezone, administrator workspace settings | Provider configuration/SMTP are deployment operations; no fake weekly digest toggle |
| Attachments | Server size/type/content checks, related-record access, private object path, 60-second signed URL, deletion integrity | Contract-tested; real cloud bucket/key setup and upload/download verification pending |

## Live database work and data integrity

The configured connection matches existing Supabase project `hazrihbiqsflnmlcycen`. Migration revision advanced from `0aa836556f2a` to `f8b3015a0001`. Before migration, an encrypted custom-format public-schema backup was saved under ignored `backend/.backups` and its archive listing verified. Counts of all 14 original application tables were unchanged after migration. No business data, test accounts or fictional records were inserted into production.

The security review independently confirmed anonymous table access before remediation. RLS and privilege revocation now prevent direct browser access, while FastAPI continues using its trusted PostgreSQL role and enforces authorization. Supabase's remaining informational **RLS Enabled No Policy** notices describe intentional default-deny browser access; broad read policies must not be added to suppress them. [Supabase explanation](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).

The backup protects public application tables. Supabase-managed Auth/Storage have separate backup requirements. Archive listing verification is not a full restore rehearsal. Keep the original session encryption secret with protected recovery material. Prefer application rollback with the additive schema retained; production downgrade would discard new feature data.

The deployment remains a single workspace. Organizations/memberships and cross-organization tenancy were not added to a product without an organization-switching feature. Workspaces requiring independent tenant isolation need separate deployments/databases until an explicit tenant migration is designed. Notes are stored as actual note activities, and organization settings as the workspace settings row.

## Local performance baseline

One additional Chromium performance test passed. Dashboard readiness, including the network-idle wait, was **{perf['dashboard_ready_ms']} ms**. Navigation TTFB was **{perf['navigation']['ttfb_ms']:.1f} ms**. Thirty paged API reads with five concurrent readers had **{perf['api']['failures']} failures**, **{perf['api']['median_ms']} ms median** and **{perf['api']['p95_ms']} ms p95**.

This is a local loopback, empty-dataset, development-authentication baseline using SQLite. It does not establish hosted capacity, cold-start latency, mobile-network performance, large-dataset performance, real Supabase Auth latency or an availability SLA. No production stress test was performed.

## Disposition of the original 23 defect groups

“Fixed locally” means implemented and verified in the stated isolated scope, not a claim that the old public Vercel deployment contains the fix.

| ID | Original severity | Original issue | Current disposition |
|---|---|---|---|
{rows}

## Open release blockers and limits

1. **High — Vercel project access.** `b2-b-crm` is visible, but the connector returns 403 for scope `salman-yousafzais-projects`. CLI fallback has no authenticated credentials. No new build/deployment ID was created. The existing public URL is not evidence that this implementation is deployed.
2. **High — administrator/Auth setup.** `salmanyousafzai736@gmail.com` is absent from CRM and Supabase Auth. Configure server-only `SUPABASE_SERVICE_ROLE_KEY`, Auth URLs, the token-hash Invite/Recovery email templates and reliable email delivery; then invite this administrator and verify the real inbox flow. No password is hardcoded and no password bypass was introduced.
3. **High — private Storage.** Create/configure the private `crm-attachments` bucket and privileged server access, then verify actual upload/download and access denial in staging. Uploads currently explain that Storage is not configured.
4. **Release verification pending.** Protected preview build, clean-route refreshes, hosted CSP/secure cookies, actual provider refresh/revocation, production logs and cloud performance must be verified before promotion. Vercel CLI detected the frontend/backend service configuration locally, but a Windows path-with-spaces quoting error in its uv launcher prevented a complete local Vercel runtime check.
5. **Explicit limits.** User/audit and related overview panels are bounded to recent records; sales record lists have tested server pagination. Automated accessibility does not replace manual screen-reader/assistive-device review. Serverless reminder delivery occurs when notifications are fetched. Multi-currency accounting, multitenancy, SSO and email campaigns are not available product features.

Full environment variables, administrator bootstrap commands, provider email templates, migration/rollback guidance and release order are in [PRODUCTION_SETUP.md](../../PRODUCTION_SETUP.md). No production-ready sign-off is issued while these blockers remain.

## Evidence files

- [Final functional browser JSON](browser-final-functional.json)
- [SQLite backend test log](backend-sqlite-tests.log) and [PostgreSQL test log](postgres-tests.log)
- [PostgreSQL verification](postgres-verification.json) and [migration log](postgres-migration.log)
- [Anonymous access before](security-live-before.json) / [after](security-live-after.json)
- [Local performance measurements](local-performance.json)
- [Python dependency audit](python-dependency-audit.json) / [npm audit](npm-audit.json)
- [Desktop dashboard screenshot](dashboard-1440.png) / [phone dashboard screenshot](dashboard-375.png)

Screenshots display explicitly isolated synthetic QA fixtures. They do not represent production customers or seed data shipped to new accounts.
'''
name='CRM_Pro_Implementation_QA_Report_2026-10-15'
(OUT/(name+'.md')).write_text(md,encoding='utf-8')
content=MarkdownIt('commonmark').enable('table').render(md)
css='''body{margin:0;background:#f5f5fc;color:#20243b;font:15px/1.65 system-ui,sans-serif}main{max-width:1160px;margin:32px auto;padding:42px;background:white;border:1px solid #dcdcec;border-radius:16px}h1{font-size:30px;color:#4231c6;line-height:1.2}h2{font-size:22px;margin-top:38px;border-bottom:1px solid #ddddef;padding-bottom:8px}table{border-collapse:collapse;width:100%;font-size:13px;margin:20px 0}th{background:#ece9ff;text-align:left}td,th{border:1px solid #dddded;padding:10px;vertical-align:top}tr:nth-child(even){background:#fafaff}code{background:#f0eff8;padding:2px 4px;border-radius:4px;font-size:.9em;overflow-wrap:anywhere}a{color:#4936c8}li{margin:8px 0}strong{color:#292257}@media(max-width:700px){main{margin:0;padding:20px;border-radius:0}table{display:block;overflow:auto}h1{font-size:25px}}@media print{body{background:white}main{border:0;margin:0;padding:0}h2{break-after:avoid}tr{break-inside:avoid}a{color:inherit}}'''
(OUT/(name+'.html')).write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CRM Pro implementation QA · 15 October 2026</title><style>'+css+'</style></head><body><main>'+content+'</main></body></html>',encoding='utf-8')
print(json.dumps({'report':str(OUT/(name+'.html')),'browser_passed':stats['expected'],'postgres':pg['tests'],'original_defect_groups':len(initial)},indent=2))
