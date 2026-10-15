# Playwright QA Report

Date: 2026-09-30
Project: stitch_crm_pro_enterprise_suite
Application URL: http://127.0.0.1:5173
API mode: Mocked Playwright routes for safe E2E execution; no production data was modified.

## A. Environment

- OS: Microsoft Windows 11 Pro
- Node: v26.2.0
- Frontend framework: Vite static HTML application with ES modules
- Backend framework: FastAPI, inspected but not required for mocked E2E run
- Playwright: 1.63.0
- Chromium execution: system Chrome 154.0.8037.92 via Playwright channel `chrome`
- Firefox/WebKit execution: blocked because Playwright browser downloads timed out from the CDN
- Failure artifacts: screenshots and traces enabled; video disabled only for this local run with `PW_VIDEO=off` because Playwright ffmpeg download also timed out

## B. Test Summary

Full command: `PW_VIDEO=off npx.cmd playwright test`

- Total: 76
- Passed: 18
- Failed: 56
- Skipped: 2
- Blocked/environment failures: 38 of the failed tests were Firefox/WebKit browser-binary failures
- Confirmed Chromium/mobile Chromium app failures: 18

By project:

- Chromium: 19 total, 10 passed, 8 failed, 1 skipped
- Mobile Chromium: 19 total, 8 passed, 10 failed, 1 skipped
- Firefox: 19 total, 19 failed due missing Playwright Firefox binary
- WebKit: 19 total, 19 failed due missing Playwright WebKit binary

## C. Module Results

Authentication:
- Valid login posts URL-encoded credentials, stores token, redirects to dashboard: Passed on Chromium and mobile Chromium.
- Invalid password renders backend error and stays on login: Passed on Chromium and mobile Chromium.
- Empty required credentials are blocked before network login: Passed on Chromium and mobile Chromium.
- Logout clears session and redirects to login: Passed on Chromium and mobile Chromium.
- Protected route redirect and viewer RBAC gate: Passed on Chromium and mobile Chromium.
- Firefox/WebKit: Blocked by missing browser binaries.

Dashboard / Analytics Overview:
- KPI summary values loaded from `/dashboard/summary`: Passed on Chromium and mobile Chromium.
- Deeper report sections for sales/lead/activity data: Failed. The HTML does not expose `data-section` targets used by `dashboard.js`, so detailed API-backed report sections are not rendered.

Companies:
- API-backed company row render: Failed. Static table rows remain visible instead of mocked API data.
- Create modal opens/submits: Failed. `#company-modal` is not injected/opened.
- Evidence: `test-results/companies-companies-compan-54906-out-uncaught-browser-errors-chromium/trace.zip`, `test-results/companies-companies-compan-3b981-ned-cancelled-and-submitted-chromium/trace.zip`.

Contacts:
- API-backed contact row render: Failed. Mocked contact `Sarah Johnson` did not appear.

Leads:
- API-backed lead row render/filter path: Failed. Mocked lead `Enterprise CRM Rollout` did not appear.

Deals / Pipeline:
- Pipeline board renders stages and deal cards: Failed. Stage text exists, but mocked deal card `Acme Expansion` did not render.

Tasks / Activities:
- Tasks table and activity feed render mocked API data: Failed. Mocked task/activity text did not appear.

Search:
- Desktop Chromium global search request and grouped result render: Passed.
- Mobile Chromium search: Failed because the matched search input was hidden at mobile viewport.

Navigation:
- Desktop Chromium sidebar link rebinding: Passed.
- Mobile Chromium navigation: Failed because the desktop sidebar link was not visible/clickable at mobile viewport.

Exports:
- Skipped on Chromium and mobile Chromium. No current HTML page contains `data-export`, while `exports.js` only binds `[data-export]` controls.

## D. Bugs Discovered

Bug ID: E2E-BUG-001
Title: Dynamic CRM module initialization does not complete on core CRUD pages
Module: Companies, Contacts, Leads, Deals/Pipeline, Tasks/Activities
Severity: High
Priority: High
Steps to reproduce:
1. Run `PW_VIDEO=off npx.cmd playwright test --project=chromium`.
2. Inspect failures for companies, contacts, leads, deals, tasks, and activities specs.
Expected result: Authenticated pages replace static placeholder content with API-backed data and wire create/edit controls.
Actual result: Static page content remains; mocked API records do not render; modals such as `#company-modal` are not created.
Evidence: Repeated Chromium failures plus invalid selector usage in `js/companies.js:22`, `js/companies.js:149`, `js/contacts.js:127`, `js/leads.js:175`, `js/pipeline.js:203`, `js/tasks.js:183`, `js/tasks.js:260`.
Suggested fix: Replace invalid `:contains()` selectors with supported selectors or explicit `data-action` attributes in the HTML, then bind those stable attributes.

Bug ID: E2E-BUG-002
Title: Export buttons are not wired to export handler
Module: Exports / Reports
Severity: Medium
Priority: Medium
Steps to reproduce:
1. Search frontend HTML for `data-export`.
2. Run exports Playwright spec.
Expected result: Export buttons expose `data-export="companies"`, `data-export="leads"`, etc., and trigger `downloadCsvExport()`.
Actual result: No `data-export` attributes exist, so `initExportButtons()` has no controls to bind.
Evidence: `Select-String` found no `data-export` in any `code.html`; Playwright export test skipped with explicit blocker.
Suggested fix: Add stable `data-export` attributes to real export buttons and verify `/exports/{entity}` download behavior.

Bug ID: E2E-BUG-003
Title: Detailed analytics sections are not connected to dashboard render targets
Module: Reports / Analytics
Severity: Medium
Priority: Medium
Steps to reproduce:
1. Run reports Playwright spec.
2. Search `analytics_reports_crm_pro/code.html` for `data-section`.
Expected result: Sales performance, lead analytics, pipeline analytics, revenue trend, activity summary, and team performance containers render API-backed data.
Actual result: No `data-section` containers exist in the analytics HTML, so `dashboard.js` has nowhere to render those sections.
Evidence: No `data-section` matches in `analytics_reports_crm_pro/code.html`; report spec cannot find mocked `Sep 2026` data.
Suggested fix: Add the expected `data-section` hooks or update `dashboard.js` to target the existing analytics DOM.

Bug ID: E2E-BUG-004
Title: Mobile navigation/search workflows are not reachable with current selectors/layout
Module: Responsive navigation and search
Severity: Medium
Priority: Medium
Steps to reproduce:
1. Run full suite and inspect mobile Chromium failures for navigation/search.
Expected result: Mobile users can reach Companies navigation and use search.
Actual result: Companies link and company search input are hidden/not actionable at the mobile viewport used by Playwright Pixel 7.
Evidence: `navigation.spec.js` mobile timeout waiting for Companies link; `search.spec.js` mobile timeout because search input is hidden.
Suggested fix: Expose a mobile menu/search workflow and add stable controls for mobile navigation/search tests.

## E. Coverage

Covered:
- Authentication: valid login, invalid password, empty required credentials, logout, protected route redirect, session persistence, viewer RBAC gate.
- Navigation: desktop sidebar link rebinding.
- Dashboard: KPI API rendering.
- Search: desktop global search request and result rendering.
- CRUD/module surfaces: companies, contacts, leads, deals/pipeline, tasks/activities page rendering and create modal path where present.
- Reports/exports: report rendering targets and export-button wiring.
- Responsive behavior: mobile Chromium project exposed navigation/search reachability issues.
- API/network behavior: tests intercept `/api/v1/*`, verify login method/body, and validate search query requests.

Not fully covered / blocked:
- Real backend login and database CRUD were not executed because no safe local E2E credentials/database were provided; mocked API was used to avoid modifying production data.
- Firefox and WebKit execution blocked by CDN timeouts while installing Playwright browsers.
- Failure videos were blocked by Playwright ffmpeg CDN timeout; screenshots and traces were generated.

## F. Final Recommendations

Confirmed application bugs:
- Replace invalid `:contains()` selector patterns and add stable `data-action` hooks for CRUD buttons.
- Add/export `data-export` attributes for export buttons.
- Align analytics HTML containers with `dashboard.js` render targets.
- Add accessible mobile navigation/search controls and tests.

Test/environment problems:
- Run `npx.cmd playwright install` again on a network that can reach Playwright CDN to enable Firefox/WebKit.
- Run `npx.cmd playwright install ffmpeg` to restore failure videos.
- Provide safe local backend E2E credentials via `.env` if real API/database E2E coverage is desired.

## Files Created/Modified

- `package.json`: added Playwright scripts and `@playwright/test` dev dependency.
- `package-lock.json`: updated by npm install.
- `.env.example`: documented API base URL and optional E2E credential variables.
- `playwright.config.js`: added Chromium/Firefox/WebKit/mobile projects, baseURL, webServer, screenshots, traces, video configuration, HTML/JSON reporters.
- `tests/fixtures/mock-api.js`: mocked safe API data and auth/session helpers.
- `tests/auth/*.spec.js`: authentication, logout, authorization tests.
- `tests/dashboard/dashboard.spec.js`
- `tests/navigation/navigation.spec.js`
- `tests/search/search.spec.js`
- `tests/companies/companies.spec.js`
- `tests/contacts/contacts.spec.js`
- `tests/leads/leads.spec.js`
- `tests/deals/deals.spec.js`
- `tests/tasks/tasks.spec.js`
- `tests/activities/activities.spec.js`
- `tests/reports/reports.spec.js`
- `tests/exports/exports.spec.js`
- `PLAYWRIGHT_QA_REPORT.md`

## Commands Used

- `npm.cmd install --save-dev @playwright/test`
- `npx.cmd playwright test --list`
- `npx.cmd playwright install` (failed: CDN timeout)
- `npx.cmd playwright install ffmpeg` (failed: CDN timeout)
- `PW_VIDEO=off npx.cmd playwright test --project=chromium --workers=1`
- `PW_VIDEO=off npx.cmd playwright test`
- `npx.cmd playwright show-report --host 127.0.0.1 --port 9323`

## Report Location

- HTML report: `stitch_crm_pro_enterprise_suite/playwright-report/index.html`
- JSON report: `stitch_crm_pro_enterprise_suite/test-results/playwright-results.json`
- Failure screenshots/traces: `stitch_crm_pro_enterprise_suite/test-results/`
