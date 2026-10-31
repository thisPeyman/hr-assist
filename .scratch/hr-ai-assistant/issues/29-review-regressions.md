# 29: Repair ingestion/review regressions

Type: task
Status: resolved

Repair unit requested for tickets 13/14/16/20; based on integration/hr-v1 at
`5cea50c`. Keep Material UI/Emotion and current project structure.

## Scope and verification seams

- Resume/review HTTP APIs: deleting a file preserves the Candidate and Activity;
  human acceptance and PATCH creation share identity matching, reconciliation,
  latest-version retention and summary initialization. Explicit edits must be
  distinguishable from unchanged extraction fields; stale writes must fail safely.
- Rendered React routes/actions: discoverable review count, queue/history,
  partial full-profile editing, acceptance/dismissal/rescan, mail failures and
  organization forwarding settings. Persian RTL and existing MUI design retained.
- Rendered profile/diff values: Jalali date presentation without changing stored
  values or translating verbatim resume content.

Confirmed test boundaries: API and database only (user clarification 2026-10-31).
UI/date work is verified by static lint/typecheck/build; browser acceptance is
deferred. External model/scanner/storage transports remain fakes, never paid/live calls.
Candidate erasure belongs to ticket 26, not this repair.

## Comments

- 2026-10-31: Claimed in clean worktree `/tmp/opencode/hr2-review-repairs` on
  `implement/review-repairs`; HEAD and integration tip both `5cea50c` before edits.

## Answer

Implemented repair unit only, preserving Material UI and current module layout:

- File deletion keeps Candidate/Notes/Applications/Activity and appends an event.
- Review and PATCH creation reuse identity/reconciliation/latest-only retention
  and per-version summary initialization; omitted PATCH fields are retained.
- Explicit review edits use baseline checks, legacy acceptance never silently
  replaces conflicting human corrections, obsolete reviews return 409, and
  human edits supersede pending proposals. Invalid raw partial data stays immutable.
- First-class `/review` and `/settings/ingestion` routes, full partial-profile
  editor, safe preview/download, queue/history, dismissal/rescan, mail failures,
  forwarding address and shell/header counts. Diff/certificate Jalali display.

Verification (2026-10-31): red→green observed for file deletion, duplicate review
identity, missing PATCH version/summary, stale proposal replay and malformed raw
contact acceptance. Added nine public API/Postgres regression cases; existing
resume workspace test now asserts Candidate/Activity survival. Full backend:
188 passed, one existing environment failure (`boto3` absent, S3 adapter test).
Normal dependency install timed out; parent owns the authorized proxy retry.
Ruff passes. Frontend typecheck/production build passes; direct oxlint exits 0
with four existing warnings (auth/candidate/resume effects/Fast Refresh), no new
warning. `npm run lint` wrapper produced an output-parser error; direct binary
is the successful lint evidence. `git diff --check` passes.

No new UI/browser tests, no live model/mail/storage/DNS calls. Browser/mobile,
clipboard and screen-reader acceptance of the new screens are deferred by the
user's API/database-only verification scope. Full live summary semantic
evaluation remains ticket 14; Admin erasure/anonymization remains ticket 26.
