# 17: Notes, @Mentions, in-app notifications

**What to build:** Collaboration on the record. HR writes editable Notes with @Mentions attached to an Application or a Candidate; both levels get aggregated views (a Candidate's notes across all their Applications, an Application's own notes). An @Mention raises an in-app notification for the mentioned user — a bell with unread state and a notification list. In-app only: v1 sends no email notifications. (Spec §5 Notes & Activity/Collaboration, §11 screen 3.)

**Blocked by:** 12 (Board home — Roles, Applications, Stages).

**Status:** resolved

- [x] Notes creatable and editable at Application and Candidate levels, with aggregated views at both levels
- [x] @Mention inside a Note raises an in-app notification for the mentioned user
- [x] Bell + notification list surfaces unread state
- [x] No email notifications sent for mentions (in-app only in v1)

## Answer

Implemented on `implement/17-notes-notifications`, based on integration `01b93bb`.
Evolved existing CandidateNote with Application scope, fixed original author,
last-editor/edit timestamp, explicit active same-org mention UUIDs and aggregated
Candidate/Application-only API and Persian RTL MUI views. Admin/Member have full
same-org collaboration access as specified; no undocumented author-only restriction.
Inactive attribution survives while inactive users are not selectable/new recipients.

Migration0009 adds tenant composite FKs, FORCE RLS and restricted grants; inbox
SELECT/UPDATE also checks recipient user GUC. Dedupe protects repeated/concurrent
edits, new recipients only get new delivery, removed/re-added mentions preserve
existing notifications/read state. Bell lists/counts/read-unread and safe deep links;
manual/automatic Merge keep Note ids, current Application attribution and links.
Activity payload/author/time stay immutable and separate from editable Note text.
Reusable transaction-local in-app notification helper is ready for deliberate23/24
extension; no mail, Google, scheduling or ticket18 implementation was added.

Verification (agreed HTTP/API + isolated DB seam): full backend **278 passed**;
seven new collaboration tests plus extended automatic bridge-Merge regression;
`hr_app` raw SQL proves forced RLS, unset/current-recipient denial, tenant FKs and
column grants. Red→green first reproduced missing author contract; no-op concurrent
edit and no external SMTP/HTTP boundary tests pass. Ruff clean; frontend build,
25 existing utility tests and oxlint pass (same four existing warnings; existing
large-chunk build advisory). Exact setup/commands and behavioral details:
`docs/notes-and-notifications.md`, `.scratch/hr-ai-assistant/implementation.md`.

**Deferred, not passed:** browser/visual/keyboard/mobile UI acceptance and new UI
tests per user instruction. No live/paid service calls, real mail or dev DB writes.
No implementation blocker at the authorized API/database/static seam.
