# 15: NL candidate search with editable chips

**What to build:** The NL-first default interaction. HR types a query in the home header ("backend engineer, fintech, 5+ years"); one cheap LLM call parses it into a filter DSL: hard constraints (YOE thresholds, enums, negations, pipeline fields) compile to SQL, and the semantic residual runs pgvector cosine plus Postgres FTS fused by RRF over a candidate-level embedding of a synthesized "search document" (normalized fields + condensed resume text — not chunks). Filters render as editable chips; editing a chip re-runs pure SQL with no LLM call. Empty results offer one-click "relax softest constraint" using the DSL's constraint-softness. Numbers and negations never touch embeddings; `years_experience_total` is computed in Python at ingestion from role date ranges (backfilled for existing Candidates) — the LLM only emits thresholds. Indexing: `tsvector` generated column + GIN, HNSW on the vector, B-tree tenant pre-filter, `pg_trgm` on names for typo tolerance. Degradations: query-parse fail → lexical-only fallback with a toast; vector fail → structured + lexical still run. Safety: the query-parse LLM sees only the user's query string, never resume content; protected-attribute filters are blocked at the code validation layer, not just in prompts. Search covers the whole Talent Pool, including Candidates with no live Application. Parsed DSL cached per (tenant, query string). Persian and mixed fa/en queries work end to end: the query-parse prompt handles Persian (including Persian numerals and YOE phrasing), chips render Persian labels, all indexed text and queries pass Persian normalization (ZWNJ, Arabic ی/ک → Persian forms), lexical FTS runs on the normalized text with the `simple` config (Postgres ships no Persian dictionary), and `pg_trgm` typo tolerance covers Persian names. (Spec §3 Language & locale, §8.1.)

**Blocked by:** 11 (Upload → parse → Candidate in the Talent Pool).

**Status:** ready-for-agent

- [ ] NL query → interpreted filters as editable chips, results streaming behind them
- [ ] YOE and negation constraints compile to SQL and never touch embeddings; chips render them faithfully
- [ ] Editing a chip re-runs as pure SQL — no LLM re-parse; negations visible as chips
- [ ] Empty results offer working "relax softest constraint"
- [ ] Degradations hold: parse fail → lexical-only + toast; vector fail → structured + lexical still return
- [ ] Persian and mixed fa/en queries parse to correct chips (incl. YOE and negations phrased in Persian)
- [ ] Persian normalization applied to search documents and queries; lexical fallback runs on the normalized `simple` config
- [ ] Typo tolerance works on Persian names
- [ ] Protected-attribute filters rejected at the validation layer (tested); query-parse LLM receives the query string only
- [ ] `years_experience_total` computed at ingestion and backfilled; results include pool Candidates with no Application
