# 10: Org & auth walking skeleton

**What to build:** A person signs up with email + password; an Org is created and they become its first Admin and only Member. They can log in and out with cookie sessions and land on an empty app home. This slice lays the tenancy pattern every later ticket builds on: shared Postgres schema, `org_id` on every tenant-owned row, app-layer scoping plus Postgres RLS as belt-and-braces, and the React + shadcn/ui frontend on the Python backend with CI green. Admin/Member exist as roles in the data model (their powers get enforced by the tickets that add those powers). Email verification and invites are deferred — no mailbox exists yet (ticket 18) — so signup is immediately active. The slice also lays the Persian-first foundation every later screen builds on: RTL layout end-to-end, a Persian typeface, all user-facing strings in Persian from day one, and Jalali date-rendering utilities at the presentation layer (storage and APIs stay Gregorian ISO 8601). (Spec §3 Language & locale, §10.)

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Signup creates Org + User + Membership; creator is the first Admin
- [x] Login/logout with cookie sessions; argon2 hashing; auth self-rolled on a mature Python OSS library (verification-ready)
- [x] One Org per User in v1; tenant-owned tables carry `org_id`; RLS enforced alongside app-layer scoping — a test proves cross-Org access fails
- [x] React + shadcn/ui app shell renders a logged-in home screen — RTL, Persian strings, Persian typeface; no hardcoded user-facing English
- [x] Jalali date-rendering utility proven at the presentation layer; storage and APIs stay Gregorian ISO 8601
- [x] CI runs schema, API, and UI tests green end to end

## Answer

Implemented on `master` (commits `5609c8f` backend, `b66ad3f` frontend, plus CI/docs).

**Backend** (`backend/`): FastAPI + SQLAlchemy async + Alembic. Auth self-rolled on **fastapi-users 15** — its argon2 PasswordHelper (pwdlib), CookieTransport, DatabaseStrategy (sessions in `access_tokens`), and login/logout routers are used as-is; only `UserManager.create` is overridden so signup creates **Org + User + Membership(admin) + `org_created` OrgActivity atomically**, then hands back a session cookie (signup is immediately active; `is_verified` exists for ticket 18).

**Tenancy**: `orgs`/`users`/`memberships` are app-layer-scoped reference tables (`memberships.user_id` unique ⇒ one Org per User); `org_activity` is the first tenant-owned table — `org_id` column, RLS **enabled + FORCED**, policy `org_activity_isolation` keyed by the transaction-local `app.current_org_id` GUC (`app/rls.py`), app connects as non-superuser `hr_app` created by migration `0002`. All later tenant tables follow this pattern.

**Frontend** (`frontend/`): Vite + React + Tailwind v4 + shadcn/ui (RTL flag), self-hosted Vazirmatn Variable, `<html lang="fa" dir="rtl">`, every user-facing string Persian (API error codes → Persian messages in `lib/api.ts`). Logged-in home renders the app shell + Jalali "desk-diary" date. Jalali utilities (`lib/jalali.ts`, jalaali-js) convert only at render; storage/APIs stay Gregorian ISO 8601.

**Tests** (agreed seams: API + RLS + Jalali units): `backend/tests/test_schema.py` (migrations, one-org constraint, RLS flags/policy, least-privilege role), `test_rls.py` (cross-Org SELECT/INSERT/UPDATE/DELETE denied as `hr_app`; unset GUC denies), `test_auth_api.py` (signup/login/logout/me round trip), `frontend/src/lib/jalali.test.ts` (10 anchors incl. ۲۲ بهمن ۱۳۵۷, Nowruz boundaries). CI: `.github/workflows/ci.yml` (postgres:18 service) — same steps run locally via `make ci` (repo has no remote yet). No browser E2E per decision on this ticket.
