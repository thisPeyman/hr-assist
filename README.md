# AI HR Assistant

SaaS ATS, Persian-first: RTL UI, Persian strings and Jalali dates at the
presentation layer, Gregorian ISO 8601 everywhere else. Spec and tickets live
in `.scratch/hr-ai-assistant/` (v1 spec: `spec.md`).

## Layout

- `backend/` — FastAPI + SQLAlchemy (async) + Alembic on Postgres. Auth is
  self-rolled on [fastapi-users](https://fastapi-users.github.io/) (argon2 via
  pwdlib, cookie sessions stored in `access_tokens`).
- `frontend/` — Vite + React + Material UI/Emotion, RTL, self-hosted
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

## Resume ingestion (ticket 11: upload → parse → Candidate)

- **Two-layer pipeline** (spec §7.3): OSS text extraction (pypdf pre-pass →
  pdfplumber for PDFs; python-docx with a raw-XML fallback for DOCX; TXT
  trivial) feeding one strict structured-output OpenAI call (Responses API,
  `json_schema` strict). Model names live in config
  (`HR_RESUME_EXTRACT_MODEL` / `HR_RESUME_EXTRACT_MODEL_ESCALATION`; defaults
  `gpt-5.6-luna` → `gpt-6.1-sol`), prompts in versioned files
  (`app/parsing/prompts/`), and every row stores `model` + `prompt_version`
  + `schema_version`. Set `HR_OPENAI_API_KEY` to enable the paid step.
- **Nothing dropped silently**: every submitted document ends in an explicit
  terminal status — `extracted`, `needs_review`, `failed`, `not_a_resume`
  (successful OCR/visual routes record `ocr_applied`/`vision_used`). The retry
  ladder is pydantic validation → one repair-retry on the same model →
  escalation → `needs_review`.
- **Queue**: a Postgres jobs table claimed with `SELECT … FOR UPDATE SKIP
  LOCKED` (no Redis/Celery). Single uploads run the pipeline inline (sync
  path, sub-minute UX); a background loop in the app lifespan drains the
  rest. RLS stays strict except one SELECT-only policy exposing *pending*
  job rows so workers can claim across Orgs before pinning one.
- **Retention + dedupe**: original bytes, raw text, and raw model JSON are
  kept (`resume_files`/`resume_extractions`); identical files dedupe by
  SHA-256 per org. Extraction values stay verbatim in the resume's own
  language; dates normalize to ISO prefixes only when confidently Gregorian
  and render as Jalali at the presentation layer (`frontend/src/lib/profile.ts`).

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

Resume ingestion, local mock email, review queue, OCR/vision and legacy-format
setup: [docs/resume-ingestion.md](docs/resume-ingestion.md). Placeholder-only
environment values are in [backend/.env.example](backend/.env.example).

Everything CI runs, locally:

    make ci

- Backend tests target a throwaway `hr_test` database (dropped and re-migrated
  each run) as the `hr_app` role; they need the same Postgres privileges as
  the migrations. CI points `HR_TEST_ADMIN_URL`/`HR_TEST_APP_URL` at its
  postgres service (see `.github/workflows/ci.yml`).
- Frontend tests cover the Jalali utilities against known date anchors.
