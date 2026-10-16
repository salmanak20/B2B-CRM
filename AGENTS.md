# B2B CRM SaaS — Codex Instructions

Existing stack: Vite/vanilla JS frontend, FastAPI, SQLAlchemy, Alembic, Supabase PostgreSQL/Auth, Vercel Services.

Goal: Upgrade the existing single-workspace CRM into secure multi-tenant SaaS.

Rules:

- Modify existing code; never rebuild from scratch.
- Preserve current UI, authentication, real data and architecture.
- Read only files relevant to the current phase.
- Make minimal, focused changes.
- Reuse existing utilities, models, routes and tests.
- Do not introduce unrelated features or dependencies.
- Never reset, seed or destructively migrate production data.
- Use staging for schema changes and tests.
- Keep Supabase privileged keys strictly server-side.
- Do not deploy production without approval.
- Run targeted tests, not the entire suite after every small change.
- Do not generate lengthy reports or explanations.
- If blocked, stop and report the exact issue.
- Respond in at most 5 concise bullets: changed files, implementation, tests, blockers and next step.
- Complete only the requested phase. Do not start future phases.

## GitHub Workflow — Required After Every Phase

Repository: [https://github.com/salmanak20/B2B-CRM](https://github.com/salmanak20/B2B-CRM)
Development branch: feature/multi-tenant-saas

Rules:

- Work on the dedicated SaaS development branch, not main.
- Preserve uncommitted user changes and existing history.
- After each completed phase, run focused tests.
- Review git diff and exclude .env, credentials, backups, database dumps, generated secrets and temporary files.
- Stage only files belonging to the completed phase.
- Create one descriptive commit per completed phase.
- Push the commit to origin/feature/multi-tenant-saas.
- Never force push or rewrite remote history.
- Never merge into main automatically.
- Never deploy production automatically.
- If tests fail, the push fails, or unrelated changes exist, stop and report the blocker.
- Keep commit messages short and professional.
- Return commit hash, branch, push status and test summary.

Commit naming examples:
Phase 1A: feat(saas): add multi-tenant database foundation
Phase 1B: feat(saas): implement legacy tenant backfill
Phase 2: feat(saas): enforce tenant isolation
Phase 3: feat(saas): add organization role management
Phase 4: feat(saas): implement business onboarding
Phase 5: feat(saas): add platform administration
Phase 6: feat(saas): implement subscriptions
Phase 7: test(saas): verify multi-tenant platform
