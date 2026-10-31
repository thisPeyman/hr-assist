# Candidate search (ticket 15)

## Workflow and API

`/search` is the Persian RTL home; the existing board remains `/board`, linked
next to the search header and in navigation. Other workspace pages have a compact
Talent Pool search header. Login, wordmark and unknown routes lead to search.
Results link to canonical Candidate pages. No search operation moves an Application,
contacts a Candidate, or returns a fit verdict.

`POST /api/search` accepts exactly one of:

```json
{"query":"مهندس بک‌اند، ۵ سال سابقه، بدون Java"}
```

```json
{"dsl":{"filters":[{"id":"f1","field":"years_experience_total","op":"gte","value":"5","constraint_softness":0}],"semantic_query":"backend"},"relax":false,"limit":50}
```

The SSE contract delivers `filters` (DSL, mode, warnings, relaxed filter id), then
zero or more `warning`/`candidate` events and `done` (count, relax_filter_id).
Chips arrive **before** query embedding and retrieval. Results are bounded to 50
by default/100 maximum. Rank is search relevance, not Candidate suitability.

Sending a DSL is **pure SQL**: no parser and no query/document embedding call.
Residual text uses lexical search only after chip edits; the UI labels this
intentional change. Chips support field/operator/value/softness edits, removal
and addition. `relax:true` removes only the highest-softness nonzero constraint
and executes the resulting DSL. Zero-softness constraints are never automatically
relaxed; ties use current filter order. Repeated relax actions can be taken by
the human, never silently by retrieval.

## Structured-first and safety

Code validates allowlisted fields/operator combinations, bounded numeric strings,
pipeline enums and UUIDs, unique chip ids and unknown keys. Text binds use literal
`strpos`/equality, not interpolated SQL or wildcard patterns. Years comparisons
exclude unknown totals. Positive pipeline constraints must match **one** scoped
Application; negative pipeline criteria mean no matching Application anywhere for
that Candidate. A pool Candidate without Applications is still searchable.

Code rejects protected field names via the allowlist and protected fa/en aliases
in raw queries, DSL values and residuals (including Arabic chars, separator aliases,
diacritics/format controls). This is a maintained denylist, not a claim of universal
natural-language understanding. New protected paraphrases need explicit regression
cases. Protected attributes must not be added as supported fields.

Residuals reject digits/numeric words, comparator signs, negation words and terms
explicitly excluded by filters. Parser output that drops an explicit numeric or
negated condition degrades rather than sending that interpretation to embeddings.
Persian/mixed-language linguistic accuracy still needs authorized live evaluation.

The parser receives only a versioned system contract and the normalized user query
string: never Profiles, names from search results, Notes, or resume text. Successful
validated DSLs cache for 24 hours by tenant + SHA256(normalized query/model/version).
Raw query strings are not persisted. Cache rows have tenant FORCE RLS.

## Search documents and derived years

`search_documents.refresh_document` is the shared accepted-Profile projection
called by ingestion/identity reconciliation, human edits, accepted proposals,
review acceptance, resume workspace edits and Merge. Rejected/pending proposals
never replace accepted search truth. Merge cascades away the retired document.

One bounded (16,000 character) Candidate-level document combines normalized
name/headline/skills/industries/location/education and condensed **accepted**
summary + up to eight bullets per work entry. No chunks, raw unaccepted extraction,
Notes, emails or phone numbers are embedded. Condensed accepted text is deliberate:
indexing raw resume text would undo a human correction or rejected proposal.

Text normalization is NFKC, Arabic ي/ك → Persian ی/ک, Persian/Arabic digits → ASCII,
ZWNJ → space, case folding and whitespace collapse. SQL field predicates mirror
this normalization. Generated FTS uses PostgreSQL `simple`, not a nonexistent
Persian dictionary. Name similarity uses real pg_trgm.

`years_experience_total` and `experience_computed_at` persist on Candidates.
Python unions overlapping full Gregorian day intervals and floors to a tenth of a
year; no history, incomplete/invalid/Jalali/future ranges produce unknown, not an
invented precision/zero. Current roles end at computation date. Totals are snapshots,
not a continuously changing SQL clock; ingest/edit or explicit reindex refreshes
them. Per-skill experience attribution is not fabricated from unstructured bullets.

Migration0008 backfills all existing accepted Profiles/documents/years **without
provider calls**. Existing Candidates remain lexical/structured searchable while
their embeddings await explicit reindex. `POST /api/search/index` with
`{"candidate_ids":["uuid"]}` retries up to 20 same-tenant Candidates atomically;
unknown/cross-tenant ids fail404. This endpoint can invoke the configured embedding
service; do not invoke it on production without approving that provider cost/data
processing. Reading/searching never causes document re-embedding.

Document hash + model + dimensions cache successful vectors. Accepted text changes
or model/dimension changes invalidate the old vector. Failures persist `unavailable`
and cannot claim stale content/model as ready; subsequent ingest/edit/index retries.
Partial/unready model coverage is reported as a visible warning in hybrid search.

## Provider configuration

The existing locked OpenAI SDK is reused; no new dependency is necessary.
`ai/actions.py` provides a reusable strict structured-action transport (separate
from the resume extractor) and a real embeddings transport. Configure explicitly:

- `HR_SEARCH_QUERY_MODEL`, `HR_SEARCH_API_KEY`, optional `HR_SEARCH_BASE_URL`.
- `HR_SEARCH_EMBEDDING_MODEL`, `HR_SEARCH_EMBEDDING_API_KEY`, optional
  `HR_SEARCH_EMBEDDING_BASE_URL`, `HR_SEARCH_EMBEDDING_DIMENSIONS` (default1536).

Use OpenAI-compatible chat structured outputs and embeddings APIs, including
self-hosted gateways (local services may use an explicit dummy key). Model names
are not hardcoded. The embedding response must be finite, nonzero and exactly
the configured dimensions. Each request has a 15-second timeout and no implicit
SDK retries. Missing settings fail closed into visible lexical degradation; they
never synthesize vectors or perform a paid call using resume-provider settings.

Parse failure/invalid output → lexical-only with Persian warning/toast and no
embedding. Vector provider failure → SQL constraints + lexical; vector SQL errors
roll back a savepoint and rerun the same hard-filtered lexical query. Chip-only
requests never invoke either provider. No automatic paid embedding backfill exists.

## PostgreSQL availability and deployment

Deployment **requires pgvector and pg_trgm available to PostgreSQL**, with migration
rights to install extensions. CI uses `pgvector/pgvector:pg18` rather than vanilla
Postgres. Migration0008 intentionally fails transactionally when vector is absent;
do not fake semantic availability by omitting its schema. Provision the extension
package/image in the explicitly selected deployment first. No development database
was migrated by this work.

The schema installs a generated `tsvector` + GIN, GIN pg_trgm normalized-name index,
B-tree org index, and a real partial HNSW cosine expression index for1536-d vectors.
Storage is dimensionless `vector` with a dimensions check and explicit per-row
model/dimension provenance; alternate configured dimensions work with exact scans.
Create a matching partial expression index in a separate operational migration if
an alternate dimension needs ANN. HNSW supports up to2000 vector dimensions;
higher-dimensional exact storage is permitted but does not use that index.

At v1 scale retrieval deliberately materializes the tenant+hard-filter population
before either ranking leg and performs **exact** cosine scans, not global ANN
top-k then tenant filtering. FTS/trigram and cosine legs fuse via RRF (`k=60`), and
only that eligible population can appear in final results. Installed indexes are
deployment/scaling seams, not a claim that the materialized v1 plan uses ANN/GIN
on every query. Escalation: measure real tenant plans, then evaluate tenant
partitioning or pgvector iterative HNSW scans while retaining hard predicates.

## Verification boundary

Public HTTP tests run with actual isolated PostgreSQL18/pgvector and restricted
hr_app SQL; mocks occur only at external parser/embedding/SDK boundaries. Database
tests prove generated/index definitions, FORCE RLS/unset/cross-tenant writes and a
rollback-only upgrade/backfill with existing Candidates. No paid/live calls,
new browser tests, deployment, or development migration were performed.

Deferred human acceptance: Persian live-query translation/semantic quality,
keyboard/mobile/browser interaction, provider provisioning/data processing consent,
and measured p50/cost on representative production-scale data. Offline mock
latencies and fabricated vectors are not evidence for live relevance or <$0.001.
