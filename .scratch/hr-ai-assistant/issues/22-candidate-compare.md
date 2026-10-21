# 22: Candidate compare (2–4)

**What to build:** First-class comparison, no verdicts. From search results or candidate detail, HR selects 2–4 Candidates and sees two layers: a deterministic side-by-side table rendered by app code from structured fields — numbers never transcribed by the LLM — plus an LLM "key differences" block of 3–5 grounded, candidate-named bullets in Persian (table labels follow the global RTL/Persian presentation; extracted values stay verbatim in their own language). There is no winner: the block ends with "questions to ask," not recommendations. Uses the shared prompt skeleton and guardrails from ticket 14; resume content is treated as untrusted data; capped at 4 candidates. (Spec §8.3, §11 screen 3 compare entry.)

**Blocked by:** 15 (NL candidate search with editable chips — the primary selection surface).

**Status:** ready-for-agent

- [ ] Compare selectable for 2–4 Candidates from search results and candidate detail
- [ ] Table values come deterministically from structured fields; LLM never transcribes numbers
- [ ] Key-differences block is 3–5 grounded, candidate-named bullets in Persian, ending in questions to ask
- [ ] Zero ranking / winner / fit language in product surface or prompts (guardrail-tested)
