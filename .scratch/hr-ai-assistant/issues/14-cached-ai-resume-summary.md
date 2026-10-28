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


## Answer

Implemented: per-version cache including failures, ingest precomputation, regeneration activity, Persian/120-180-word validation, missing fields, guardrails, overlap-safe experience calculation, versioned prompts, and 20 golden inputs. Automated contracts and browser flows pass. Initial Groq HTTP 403 cleared on retest on 2026-10-28: model access and inference succeeded, the stored resume was reprocessed, and a 173-word Persian summary was persisted with status ready. Full live semantic evaluation of all 20 golden cases remains pending. See [verification boundary](../../../docs/profiles-and-summaries.md).
