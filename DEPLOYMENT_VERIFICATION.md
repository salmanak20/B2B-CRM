# Vercel deployment repair — 15 October 2026

The GitHub-pushed application now builds and serves from [b2-b-crm.vercel.app](https://b2-b-crm.vercel.app/login), including its FastAPI backend and existing Supabase PostgreSQL database.

## Failure and changes

Failed deployment `dpl_6D24gvdEeY9h4wRS1kugBrTps2qy`, commit `cf915b8`, reported:

```text
Skipping "install" command...
> vite build
sh: line 1: vite: command not found
Error: Command "npm run build" exited with 127
```

- Reset the existing Vercel project's root to the repository root and cleared legacy project-level install/build/output overrides. The root Services configuration now owns both frontend and backend builds.
- Added explicit `npm ci --include=dev` installation to the frontend configuration and generator, so Vite is installed even with a production environment. Retained Node.js 24 and pinned Python 3.12 to the tested runtime.
- Configured required production database/session/Auth environment variables privately and preserved the server service key already added in the dashboard. No secrets were committed or printed in the report/chat.
- The first repaired build reached READY and passed API/database checks, but the subsequent page checks caught `cleanUrls` redirects ending in 404. Changed service rewrites to exact built `.html` destinations and disabled implicit clean-URL redirects. Public clean routes and both legacy URL forms now resolve.

Source repair commits: [`5416a88`](https://github.com/salmanak20/B2B-CRM/commit/5416a88433864ae29c828c848d52b1a2eff91231) and [`de1f900`](https://github.com/salmanak20/B2B-CRM/commit/de1f900bf8ea3e816882215b259450b7155bd62d).

## Verified deployment

- **Project:** `b2-b-crm` / `prj_qpzgCm1EHryhz6kfC0TB5K45NTYR`
- **Deployment:** `dpl_DJMHZYLPkP2iCHsLpEfsD2N9Mz2t`
- **Target/status:** production / READY
- **URL:** [production login](https://b2-b-crm.vercel.app/login)
- **Frameworks:** Vite frontend + FastAPI backend through Vercel Services
- **Build/runtime:** frontend compiled, Python dependencies installed and bytecode compiled; live backend DB connection succeeded

| Boundary | Evidence |
|---|---|
| Build/install | Local clean install, production build and shipped-asset check passed; Vercel installed and built both services |
| UI/page routing | All standard app pages, root, legacy login URL forms and contact HTML URL returned 200 |
| Browser rendering | Live login form rendered with real Supabase recovery availability; JS/CSS assets returned 200 |
| Browser → API | `/api/v1/auth/config` returned 200 with `provider=supabase`, 8-hour standard session and 30-day Remember Me policy |
| API → database | `/api/v1/health/ready` returned 200 and `{"status":"ready"}` |
| Access denial | `/api/v1/auth/me` returned 401 with `Please sign in` without credentials |
| Security headers | CSP present on checked page/API responses |
| Post-deploy errors | No error/fatal runtime log records returned for this deployment in the checked 15-minute window |

[Read-only smoke evidence](qa-results/implementation/vercel-deployment-smoke.json) records all 23 URL checks. [Browser screenshot](qa-results/implementation/production-login-deployed.png) records the deployed login page.

## Remaining account setup

Deployment success is separate from initial account provisioning. The requested administrator email is still absent from Supabase Auth. Its invitation/profile linking, actual email recovery delivery/templates, authenticated secure-cookie flow and real private Storage operations still require verification. No production customer fixture or test account was inserted during this repair. See [production setup](PRODUCTION_SETUP.md) for the secure bootstrap method.
