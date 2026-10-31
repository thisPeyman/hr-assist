# 15: NL candidate search with editable chips

**What to build:** The NL-first default interaction. HR types a query in the home header ("backend engineer, fintech, 5+ years"); one cheap LLM call parses it into a filter DSL: hard constraints (YOE thresholds, enums, negations, pipeline fields) compile to SQL, and the semantic residual runs pgvector cosine plus Postgres FTS fused by RRF over a candidate-level embedding of a synthesized "search document" (normalized fields + condensed resume text — not chunks). Filters render as editable chips; editing a chip re-runs pure SQL with no LLM call. Empty results offer one-click "relax softest constraint" using the DSL's constraint-softness. Numbers and negations never touch embeddings; `years_experience_total` is computed in Python at ingestion from role date ranges (backfilled for existing Candidates) — the LLM only emits thresholds. Indexing: `tsvector` generated column + GIN, HNSW on the vector, B-tree tenant pre-filter, `pg_trgm` on names for typo tolerance. Degradations: query-parse fail → lexical-only fallback with a toast; vector fail → structured + lexical still run. Safety: the query-parse LLM sees only the user's query string, never resume content; protected-attribute filters are blocked at the code validation layer, not just in prompts. Search covers the whole Talent Pool, including Candidates with no live Application. Parsed DSL cached per (tenant, query string). Persian and mixed fa/en queries work end to end: the query-parse prompt handles Persian (including Persian numerals and YOE phrasing), chips render Persian labels, all indexed text and queries pass Persian normalization (ZWNJ, Arabic ی/ک → Persian forms), lexical FTS runs on the normalized text with the `simple` config (Postgres ships no Persian dictionary), and `pg_trgm` typo tolerance covers Persian names. (Spec §3 Language & locale, §8.1.)

**Blocked by:** 11 (Upload → parse → Candidate in the Talent Pool).

**Status:** ready-for-human

- [ ] NL query → interpreted filters as editable chips, results streaming behind them
- [x] YOE and negation constraints compile to SQL and never touch embeddings; chips render them faithfully
- [x] Editing a chip re-runs as pure SQL — no LLM re-parse; negations visible as chips
- [x] Empty results offer working "relax softest constraint"
- [x] Degradations hold: parse fail → lexical-only + toast; vector fail → structured + lexical still return
- [ ] Persian and mixed fa/en queries parse to correct chips (incl. YOE and negations phrased in Persian)
- [x] Persian normalization applied to search documents and queries; lexical fallback runs on the normalized `simple` config
- [x] Typo tolerance works on Persian names
- [x] Protected-attribute filters rejected at the validation layer (tested); query-parse LLM receives the query string only
- [x] `years_experience_total` computed at ingestion and backfilled; results include pool Candidates with no Application

### Implementable API/database criteria

- [x] Configurable real structured-action and embedding adapters reuse the locked
  OpenAI SDK; public HTTP tests mock only external adapters/SDK, not SQL retrieval.
- [x] Validated numeric/text/pipeline DSL, same-Application positive predicates,
  any-matching negative exclusions, literal bound values and tenant24h DSL cache.
- [x] Filters-first SSE, real cosine/FTS/trigram RRF, tenant+hard-filter population
  materialized before ranking, pure-SQL chip requests and actual one-filter relax.
- [x] Accepted-Profile projection refreshes through ingestion, human edits, proposal
  acceptance, review and Merge; conservative unioned YOE persists/backfills.
- [x] Migration0008 installs generated `simple` FTS/GIN, name trgm/GIN, tenant
  B-tree, real1536-d HNSW, dimension/model provenance and FORCE RLS; provider-free
  backfill and bounded explicit indexing/retry. CI uses actual pgvector Postgres.
- [x] Persian MUI search home/header, results, editable/negated chips, softness,
  relaxation, warnings/toast and canonical Candidate links; board retained.
- [x] Full backend suite, Ruff, frontend static build/lint and existing utility tests.

### Genuinely pending original acceptance

- [ ] Browser/keyboard/mobile RTL acceptance of streamed chips/results, edits,
  empty-state relaxation, degradation toast and Candidate/board navigation.
- [ ] Authorized live Persian/mixed fa/en query evaluation (including numeric
  phrases and negations), semantic quality and representative measured p50/cost.
- [ ] Deployment provisioning of pgvector and explicitly approved search providers,
  credentials and candidate-document data processing/embedding backfill costs.

## Answer

Ticket15's implementable API/database and static frontend scope is complete;
**full15 remains ready-for-human**, not resolved. The two combined live/UI criteria
above remain unchecked: mocked parser output is not evidence of real Persian
translation or browser behavior. No paid/live calls, new browser/UI tests,
development database migration or deployment were performed.

`POST /api/search` accepts either NL or a validated DSL and streams filters before
embedding/retrieval, then warnings/results/completion. Explicit DSL requests use
SQL only; relaxation removes the declared softest nonzero filter, never strict
constraints. Missing/invalid parser output visibly degrades to lexical search;
vector failures preserve hard-filtered lexical search, including savepoint recovery
after real vector SQL errors. Protected fa/en aliases are blocked in code; this
maintained denylist is not universal natural-language understanding.

Migration0008 backfills normalized accepted documents and conservative years with
no provider calls. Ingestion/edit/review/Merge share document refresh, content/model/
dimension cache invalidation and explicit retry via `/api/search/index`. At v1 scale
cosine ranking intentionally scans the exact eligible population; the installed
partial HNSW is real but not claimed as the active ANN retrieval plan.

Verification (2026-10-31): isolated PostgreSQL18/pgvector, restricted `hr_app`:
**271 backend tests passed**, including49 new search HTTP/database cases; Ruff
clean. Frontend TypeScript/Vite production build passed;25 existing utility tests
passed; direct oxlint zero errors/four pre-existing warnings. Existing >500kB main
chunk warning remains; search route is lazy-loaded. Deployment/configuration,
snapshot semantics, safety limits and human release gates:
[candidate-search.md](../../../docs/candidate-search.md).
