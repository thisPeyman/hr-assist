# 14: Cached AI resume summary

**What to build:** Opening a Candidate shows a precomputed summary card: headline; current title/employer; total years; key skills; notable employers/industries; education; languages; locations — plus an "unclear or missing" list so extraction gaps stay visible. 120–180 words, non-evaluative, in Persian — even when the grounding resume is English. The summary runs once per resume version and is cached (a new resume version regenerates it); manual regeneration appends an "AI summary regenerated" Activity entry. This ticket introduces the shared prompt skeleton every later AI action reuses — system (role/audience/tone) → grounding block (structured fields + targeted excerpts, never the whole blob) → output contract → guardrails — with prompts as versioned files and a small golden set run on prompt changes. Guardrails hold: every claim traces to provided data; unknown → "not stated in resume"; never infer or mention protected characteristics; descriptive, never evaluative. (Spec §8 preamble, §8.2.)

**Blocked by:** 11 (Upload → parse → Candidate in the Talent Pool).

**Status:** ready-for-human

- [x] Summary card renders on candidate detail from cache; not recomputed on every view
- [x] Cached per resume version; a new resume regenerates; manual regenerate appends Activity
- [ ] Summary text is Persian regardless of resume language (golden-set case with an English resume)
- [x] Includes the "unclear or missing" list, in Persian
- [ ] 120–180 words, non-evaluative; golden-set cases show "not stated in resume" rather than invention
- [x] Shared prompt skeleton + versioned prompt files + golden set in place, reusable by later AI tickets

### Implementable API/database criteria (contract v2)

- [x] All required categories have application-owned supplied/partial/unknown facts
  and persisted source-path/value evidence, distinct from unverified model prose.
- [x] Multiple explicit current jobs, historical-only jobs, nested empties, unknown
  years, residence/work locations and absent industries handled deterministically.
- [x] Per-SHA cache, no paid GET/backfill, legacy-unverified content and repair29
  behavior preserved; failed forced generation retains successful provenance.
- [x] Strict provider output, absent/invalid evidence and explicit forbidden outputs
  rejected with one repair; safe cached failure; real adapters tested at mocked SDK
  boundary through HTTP for Responses/chat, configured model and summary guidance.
- [x] Persian MUI category panel implemented; static build/lint + existing tests.

### Genuinely pending original acceptance (not implementation blockers)

- [ ] UI/browser acceptance: responsive RTL and keyboard review of categories,
  unknown/partial states, legacy warning, failed regeneration/retained content.
- [ ] Authorized live generation of all20 fixtures with recorded date/provider/
  model/v2 prompt and per-case Persian human review of factual prose coverage,
  unknown-vs-negative statements, non-invention, protected attributes and
  non-evaluation. Automatic contract checks are not a semantic oracle.


## Answer

API/database implementation complete; **full14 remains ready-for-human**, not
resolved. Contract v2 adds deterministic categories and minimal persisted evidence,
cache-only legacy handling, retained-success provenance and action-aware transport
repair. Persian MUI exposes the categories and honestly labels snapshot/legacy/
failure states. Code enforces structural, syntactic and explicit phrase checks,
not arbitrary prose factuality; generic valid prose can still pass while reliable
category coverage is provided separately. No new browser tests or live calls.

Historical Groq403 recovered on 2026-10-28 with one stored173-word v1 Persian
summary; this is **not** all20-case or v2 semantic acceptance. Original combined
Persian/prose/non-invention criteria above remain unchecked until human/live
verification. See [contract, snapshot semantics and verification boundary](../../../docs/profiles-and-summaries.md).

## Comments

- 2026-10-31: Implementer claimed only the remaining14 API/database unit on
  `implement/14-summary-contract` from integration `1fa1c5e`; no ticket15 scope.
  Public HTTP/isolated Postgres red→green: missing coverage first failed with
  `KeyError: coverage_status`; retained provenance failed because old content was
  labeled `new-model`; mocked Responses/chat repair failed on extraction guidance.
  All repaired. Detailed final test counts/commands recorded in implementation log.

- 2026-10-31: [Repair 29](29-review-regressions.md) initializes versions and
  precomputed summaries on human review acceptance and PATCH creation as well
  as automated ingest. HTTP regressions cover cached success and failure without
  blocking acceptance. No live model calls; full live semantic evaluation and
  the remaining ticket-14 verification unit are not completed by this repair.
