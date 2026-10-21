# 10: Org & auth walking skeleton

**What to build:** A person signs up with email + password; an Org is created and they become its first Admin and only Member. They can log in and out with cookie sessions and land on an empty app home. This slice lays the tenancy pattern every later ticket builds on: shared Postgres schema, `org_id` on every tenant-owned row, app-layer scoping plus Postgres RLS as belt-and-braces, and the React + shadcn/ui frontend on the Python backend with CI green. Admin/Member exist as roles in the data model (their powers get enforced by the tickets that add those powers). Email verification and invites are deferred — no mailbox exists yet (ticket 18) — so signup is immediately active. The slice also lays the Persian-first foundation every later screen builds on: RTL layout end-to-end, a Persian typeface, all user-facing strings in Persian from day one, and Jalali date-rendering utilities at the presentation layer (storage and APIs stay Gregorian ISO 8601). (Spec §3 Language & locale, §10.)

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Signup creates Org + User + Membership; creator is the first Admin
- [ ] Login/logout with cookie sessions; argon2 hashing; auth self-rolled on a mature Python OSS library (verification-ready)
- [ ] One Org per User in v1; tenant-owned tables carry `org_id`; RLS enforced alongside app-layer scoping — a test proves cross-Org access fails
- [ ] React + shadcn/ui app shell renders a logged-in home screen — RTL, Persian strings, Persian typeface; no hardcoded user-facing English
- [ ] Jalali date-rendering utility proven at the presentation layer; storage and APIs stay Gregorian ISO 8601
- [ ] CI runs schema, API, and UI tests green end to end
