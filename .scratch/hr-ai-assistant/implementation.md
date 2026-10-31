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
- Ticket [12](issues/12-board-roles-applications-stages.md): implemented board home,
  Roles Draft→Open and independent optional Owners, canonical Applications,
  explicit stale-safe stage moves/context/reasons and same-id ending reopen;
  MUI Persian RTL board/Role pages, right-edge collapsed endings, candidate
  sourcing and navigable detail integration. Migration0007 preserves placeholder
  Application ids/JSON and distinct Role identity; Merge coalesces same-Role
  candidacies and preserves notes/history/source state without an automatic move.
  API/isolated Docker Postgres full backend **199 passed**; Ruff clean; frontend
  build, 25 existing utility tests and oxlint pass (four pre-existing warnings).
  Browser/UI/live checks deferred by user choice; no dev DB writes/services.
  Reusable/future-child boundary and ticket25/26 caveats: `docs/pipeline.md`.
- Shared dependency blocker **cleared** by coordinator: bounded SOCKS downloads
  verified against `backend/uv.lock`, installed boto3/botocore/jmespath/s3transfer
  and python-dateutil/six; imports and `uv pip check` compatible. Ticket12's own
  full backend run includes passing existing S3 adapter. Historical repair188-pass
  count above is retained as the evidence available at repair time.
- Ticket [14](issues/14-cached-ai-resume-summary.md), contract v2 (2026-10-31):
  implementable API/database criteria complete; full original ticket remains
  **ready-for-human**, with UI/browser and authorized live20-case Persian semantic
  acceptance explicitly unchecked. Added deterministic category facts and minimal
  evidence snapshots, multiple-current/partial/unknown states, residence/work
  locations, cache-only legacy labeling and preserved successful provenance after
  failed force. No SQL migration, live calls, paid GET/backfill, new browser tests
  or ticket15 scope. Persian MUI renders reliable categories separately from prose.
  Versioned v2 instructions and strict schema; provider output cannot author facts,
  employer or years fields; absent evidence and explicit forbidden phrases reject
  with one repair. This does not prove arbitrary prose factuality or semantics.
  - Red→green through HTTP/Postgres: missing coverage (`coverage_status` KeyError),
    failed-force old content relabeled `new-model`, SDK-boundary Responses/chat
    summary repair using extraction guidance. Additional boundary regression:
    valid20-model-gap output plus deterministic gaps previously errored on storage;
    generated contract now allows the bounded32 combined labels.
  - Exact backend command from worktree `backend/`:
    `HR_TEST_ADMIN_URL='postgresql+asyncpg://postgres:hr_v1_test_only@127.0.0.1:56432/postgres' HR_TEST_APP_URL='postgresql+asyncpg://hr_app:hr_app_dev@127.0.0.1:56432/hr_test' /home/peyman/Projects/me/hr2/backend/.venv/bin/python -m pytest -q`.
    Uses only disposable Docker `hr_test`, never host/dev database. Final full
    suite **222 passed** (includes existing repair29/pipeline tests). Focused
    `tests/test_summary_contract.py tests/test_profile_merge_summary.py`:53 passed,
    including23 new parametrized public HTTP/actual Postgres cases with only
    provider/SDK external boundaries mocked.
  - `/home/peyman/Projects/me/hr2/backend/.venv/bin/ruff check app tests migrations scripts`:
    clean. `npm run build`:pass. `npm test`:25 existing utility tests pass.
    `npx --no-install oxlint`:zero errors, same four pre-existing warnings.
    Frontend uses ignored symlink to main `node_modules`; no new dependencies.
  - `/home/peyman/Projects/me/hr2/backend/.venv/bin/python -m scripts.eval_resume_summary --output /tmp/opencode/hr-v1-summary-v2-offline.json`:
    all20 deterministic expectations/gaps pass, explicitly labeled
    `offline_deterministic_only` / semantic acceptance NOT_EVALUATED. No `--live`.
    Every fixture now has literal category expectations; overlap4.0 vs incomplete
    years unknown are distinct. Future live mode records date/provider/model/
    prompt/output for human review, not semantic PASS.
  - Snapshot/legacy/provenance/validation semantics and exact human release gate:
    `docs/profiles-and-summaries.md`. Ticket Answer/map updated without resolving
    original semantic or UI criteria. Integration tip `1fa1c5e` checked before
    implementation and merged before delivery (already ancestor/current).

- Ticket [15](issues/15-nl-search-editable-chips.md) (2026-10-31): implementable
  API/database and static frontend scope complete; **full15 ready-for-human** for
  authorized live Persian semantic quality, browser/keyboard/mobile acceptance and
  deployment/provider approvals. Search is home, `/board` remains prominent.
  - Real configurable structured-action/embedding adapters reuse locked OpenAI SDK;
    no dependencies/lockfile changes. Validated numeric/negated/pipeline DSL,
    protected fa/en alias denylist, tenant24h cache, filters-first SSE, SQL-only chip
    edits and actual softest-nonzero relaxation. Vector SQL savepoint recovery keeps
    the same tenant/hard-filter lexical population; no synthetic vectors in runtime.
  - Accepted-Profile documents and conservative unioned Gregorian YOE refresh across
    ingestion/edits/accepted proposals/review/Merge. Migration0008 provides provider-
    free backfill, generated FTS/GIN, trgm/GIN, B-tree, real partial1536-d HNSW and
    FORCE RLS. Exact materialized eligible-population cosine/RRF is deliberate for
    v1; explicit bounded `/api/search/index` retries/backfills embeddings. Ordinary
    search never embeds documents. CI now uses `pgvector/pgvector:pg18`.
  - Final full backend command uses the same isolated Docker URLs documented for14:
    **271 passed** (49 new public HTTP/real SQL/schema/backfill cases),58.55s.
    `/home/peyman/Projects/me/hr2/backend/.venv/bin/ruff check .`:clean.
    `npm run build`:pass (existing main-chunk size warning); `npm test`:25 pass;
    `./node_modules/.bin/oxlint`:zero errors/four pre-existing warnings. The
    `npm run lint` harness wrapper failed parsing output; direct oxlint succeeded.
  - No paid/live calls, new browser/UI tests, development migration or deployment.
    Configuration, exact retrieval/index seam, coverage/failure behavior, YOE
    snapshot limits and explicit human acceptance gates: `docs/candidate-search.md`.
    Integration base/current tip verified as `ff96489` before delivery.

## Review regression pointers

- `backend/app/resumes.py:251`: Member deletion silently erases Candidate and cascading Activity; remove implicit Candidate deletion and implement proper Admin erasure in ticket 26.
- `backend/app/review.py:248-286`: acceptance bypasses identity matching, protected corrections/diffs, latest-version retention and summary precomputation. Workspace PATCH creation also omits version/summary initialization.
- `frontend/src/App.tsx`: no review/ingestion-settings routes; existing API helpers have no callers. Need discoverable review count, accept/dismiss/rescan, mail failures and forwarding address.
- Raw Gregorian values in profile diffs/certification dates need existing Jalali presentation helpers.
- Four disposable regression probes at `/tmp/opencode/test_hr_latest_commit_review.py` reproduced member DELETE 204, correction overwrite, summary 409 RESUME_VERSION_MISSING, and duplicate on review acceptance. Probes assert proposed behavior; adapt to explicit human-edit semantics rather than treating every submitted field as a new override.
- Baseline tests: 179 backend pass, one missing-boto3 failure; frontend build and 25 tests pass; Worker 4 pass; offline summary grounding 20 pass.
