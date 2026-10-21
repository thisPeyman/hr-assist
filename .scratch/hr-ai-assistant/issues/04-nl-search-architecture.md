# 04 - Natural-language candidate search architecture

Type: research
Status: resolved

## Question

How should "find me a backend engineer with fintech experience and 5+ years" work over the candidate pool on Postgres + Python + OpenAI? Compare: (a) pgvector embeddings over resumes/structured summaries with hybrid keyword search, (b) LLM translating natural language → structured query over extracted candidate fields, (c) a hybrid of both. Also cover how the summary and compare prompts should be structured. Recommend a v1 architecture: index strategy, what's embedded vs. structured-field-only, latency/cost expectations, and known failure modes (e.g. years-of-experience math, negation queries).

## Context

- Related AI actions in v1: summaries, NL search, compare, draft outreach (map Notes). Ranking/scoring is out of v1.
- Feeds: the data-model decisions (05) and the spec's AI-architecture section (09).
- Findings go in `.scratch/hr-ai-assistant/research/`; link from the answer.

## Answer

**Recommendation: option (c), hybrid — with the LLM→structured-query path as the spine, not a peer.** One cheap LLM call parses each search into a filter DSL with two parts: `filters` (hard constraints — YOE thresholds, enums, negations, pipeline fields — compiled to SQL) and `semantic_query` (the soft residual, run as pgvector cosine + Postgres FTS fused by RRF). Numbers and negations are **never** trusted to embeddings; years-of-experience is computed in Python at ingestion from role date ranges, and the LLM only emits the threshold. Index: a single **candidate-level embedding of a synthesized "search document"** (normalized fields + condensed resume text — not chunks, since queries rank whole people), a generated `tsvector` + GIN index, HNSW on the vector, and B-tree tenant pre-filtering with exact vector scans at v1 scale (HNSW + iterative scans / partitioning as the documented escalation). The interpreted filters render back as **editable chips** in the GUI — turning LLM mistranslation into a correction loop — and the same "system prompt + grounding block + output contract + guardrails" skeleton structures summary (descriptive, schema'd, cached), compare (deterministic table + LLM key-differences bullets, no winner verdict), and outreach (grounded, placeholder'd, draft-only). Expect ~1s p50 latency and <$0.001 per search (Oct-2026 OpenAI pricing), <$0.01 per ingested candidate, with lexical-only degradation on API failure and a code-layer blocklist on protected-attribute filters. Key seam for tickets 02/05/09: extraction must emit normalized skills/industries and per-role date ranges; model choices stay in config.

Full findings: [../research/04-nl-search-architecture.md](../research/04-nl-search-architecture.md)
