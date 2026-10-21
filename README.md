# AI HR Assistant

SaaS ATS, Persian-first: RTL UI, Persian strings and Jalali dates at the
presentation layer, Gregorian ISO 8601 everywhere else. Spec and tickets live
in `.scratch/hr-ai-assistant/` (v1 spec: `spec.md`).

## Layout

- `backend/` — FastAPI + SQLAlchemy (async) + Alembic on Postgres. Auth is
  self-rolled on [fastapi-users](https://fastapi-users.github.io/) (argon2 via
  pwdlib, cookie sessions stored in `access_tokens`).
- `frontend/` — Vite + React + Tailwind v4 + shadcn/ui, RTL, self-hosted
  Vazirmatn, Jalali rendering via jalaali-js.

## Tenancy model (v1: one Org per User)

- Tables: `orgs`, `users`, `memberships` (unique `user_id` ⇒ one org per
  user), plus `org_activity` — the first tenant-owned data table.
- Every tenant-owned row carries `org_id`; the app scopes queries per request
  **and** Postgres RLS denies anything else: migration `0002` creates the
  non-superuser `hr_app` role the app connects as, and enables + FORCEs row
  level security on `org_activity` keyed by the `app.current_org_id` GUC.
- The request layer pins that GUC per transaction
  (`app/rls.py` → `set_current_org`), so it can never leak across pooled
  connections. Later tenant tables (candidates, roles, applications, …)
  follow the same pattern.
- Tests prove isolation twice: raw-SQL cross-Org SELECT/INSERT/UPDATE/DELETE
  probes as `hr_app` (`backend/tests/test_rls.py`), and the HTTP signup →
  login → logout → me flow (`backend/tests/test_auth_api.py`).

## Local setup

Requirements: Python 3.14 ([uv](https://docs.astral.sh/uv/)), Node 22,
PostgreSQL 15+ with superuser access for your OS user.

One-time Postgres bootstrap (peer auth on a local Ubuntu cluster):

    sudo -u postgres createuser -s "$USER"

Create the dev database and run migrations (creates the `hr_app` role and all
tables):

    psql -d postgres -c 'create database hr_dev'
    cd backend
    HR_MIGRATION_DATABASE_URL="postgresql+asyncpg://$USER@/hr_dev?host=/var/run/postgresql" \
      uv run alembic upgrade head

Run the backend (pick a free port; the frontend dev proxy defaults to 8000 —
if 8000 is taken, adjust `server.proxy` in `frontend/vite.config.ts`):

    cd backend && uv sync
    HR_COOKIE_SECURE=false uv run fastapi dev app/main.py --port 8000

Run the frontend dev server (proxies `/api` and `/auth` to the backend):

    cd frontend && npm install && npm run dev

The built SPA is also served by the backend itself (`app.frontend()`) whenever
`frontend/dist` exists: `npm run build` then open the backend port.

## Tests / CI

Everything CI runs, locally:

    make ci

- Backend tests target a throwaway `hr_test` database (dropped and re-migrated
  each run) as the `hr_app` role; they need the same Postgres privileges as
  the migrations. CI points `HR_TEST_ADMIN_URL`/`HR_TEST_APP_URL` at its
  postgres service (see `.github/workflows/ci.yml`).
- Frontend tests cover the Jalali utilities against known date anchors.
