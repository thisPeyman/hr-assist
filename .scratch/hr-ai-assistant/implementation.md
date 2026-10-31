# v1 implementation run

- Integration branch: `integration/hr-v1`
- Starting commit: `b7873720b332bae1e36524f3c0effc93428050ac`
- User direction: continue the current project/commit structure; implement remaining tickets one by one, continuing until done, using implement-spec.
- Preserve the current Material UI/Emotion frontend rather than reverting the latest commit's UI rewrite. Reconcile the documented stack to match this continuation decision.
- Workflow: one implementer worktree/branch per ticket, TDD, merge current integration tip before reporting; a merger agent merges completed work into integration. No remote PR is requested; local Markdown tracker is authoritative.
- Do not use real credentials, send real email, deploy infrastructure, or spend API credit for verification. Record live/human-only checks honestly as pending, not successful.
- User-confirmed test seams (2026-10-31): API and isolated database only. External Google/AI/mail adapters may be mocked through HTTP/API tests. Run static lint/build, but defer new browser/UI tests and live integration acceptance.
- User-provided network proxy: `socks5h://127.0.0.1:10808`, reachable with curl. Use command-local proxy environment variables for dependency downloads; do not change global network configuration.
- Tests recreate only `hr_test`; serialize backend test runs across worktrees. Use existing main repo Python environment if necessary; dependency synchronization currently times out downloading botocore. Frontend dependencies are installed in the main worktree.

## Sequence

1. Repair latest-commit review gaps (13/14/16/20), retaining audit and tenant protections.
2. 12 — board, roles, applications, stages.
3. 14 — finish automated summary verification; record live semantic evaluation boundary.
4. 15 — natural-language search and editable chips.
5. 17 — notes, mentions, notifications.
6. 18 — Google OAuth seam, system mailbox, user administration.
7. 19 — per-user connect and human-sent outreach.
8. 22 — candidate comparison.
9. 23 — scheduling core and booking page.
10. 24 — scheduling lifecycle and reminders.
11. 25 — endings.
12. 26 — pipeline editor, hard/soft candidate deletion.
13. 27 — optional TOTP.
14. 28 — pilot verification; final two-axis review and fixes.

## Progress

- Planning: clean main checked; integration branch created.
- Repair unit [29](issues/29-review-regressions.md): implemented current-MUI
  review/settings surfaces and API identity/correction/version/summary repairs;
  file deletion preserves Candidate and Activity. Added nine API/Postgres
  regressions, red→green on reproduced defects. Backend 188 pass / one existing
  missing-boto3 environment failure; frontend build and direct oxlint pass
  (four pre-existing warnings), Ruff passes. No UI/browser tests or live calls;
  browser acceptance and full live summary semantics remain pending. Parent
  owns proxy dependency retry; no later ticket included in this repair.
- Architecture notes for implementers: `/tmp/opencode/hr-v1-seams.md`. Local pgvector extension unavailable; `pg_trgm` available. Search ticket must provide a real pgvector-capable deployment/CI path without silently substituting fake semantics, and preserve lexical degradation when vectors are unavailable.
- Isolated pgvector test container prepared: `hr2-v1-vector-tests`, localhost port `56432`, PostgreSQL18 with vector0.8.7/pg_trgm1.6 available. Test-only connection setup: `/tmp/opencode/hr-v1-vector-test-env.md`; host/dev database untouched. Search and later migrations can be tested here.
- Additional coordinator/implementer context: `/tmp/opencode/hr-v1-agent-contract.md`, `/tmp/opencode/hr-v1-google-auth-notes.md`, `/tmp/opencode/hr-v1-acceptance-checklist.md`.

## Review regression pointers

- `backend/app/resumes.py:251`: Member deletion silently erases Candidate and cascading Activity; remove implicit Candidate deletion and implement proper Admin erasure in ticket 26.
- `backend/app/review.py:248-286`: acceptance bypasses identity matching, protected corrections/diffs, latest-version retention and summary precomputation. Workspace PATCH creation also omits version/summary initialization.
- `frontend/src/App.tsx`: no review/ingestion-settings routes; existing API helpers have no callers. Need discoverable review count, accept/dismiss/rescan, mail failures and forwarding address.
- Raw Gregorian values in profile diffs/certification dates need existing Jalali presentation helpers.
- Four disposable regression probes at `/tmp/opencode/test_hr_latest_commit_review.py` reproduced member DELETE 204, correction overwrite, summary 409 RESUME_VERSION_MISSING, and duplicate on review acceptance. Probes assert proposed behavior; adapt to explicit human-edit semantics rather than treating every submitted field as a new override.
- Baseline tests: 179 backend pass, one missing-boto3 failure; frontend build and 25 tests pass; Worker 4 pass; offline summary grounding 20 pass.
