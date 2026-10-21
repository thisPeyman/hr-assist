# Research 02 — Resume parsing pipeline (OSS extraction + OpenAI structured extraction)

Ticket: `issues/02-resume-parsing-pipeline.md` · Researched 2026-10-20/21 · Status: resolved

## TL;DR recommendation

**Two-layer pipeline: best-of-breed OSS text extraction → one OpenAI structured-output call.**

1. **Text extraction (free, local):** `pdfplumber` for PDFs (layout-aware, best reading order on two-column resumes), `pypdf` as fast pre-pass + fallback, `python-docx` for DOCX, trivial paths for TXT/HTML. Scanned PDFs detected by per-page text density → **OCRmyPDF (Tesseract)** adds a text layer → re-extract. Only if OCR still yields junk: **vision fallback** — send page images to the LLM as image input.
2. **Structured extraction (the only paid step):** a single call with **strict Structured Outputs (`json_schema`)** to a small/fast OpenAI model — **`gpt-5.6-luna` ($0.20/$1.20 per 1M in/out)** — escalating hard failures to a mid-tier model (`gpt-6.1-sol` / `gpt-5.6-sol`, $2/$10). Pydantic validation + one repair-retry before escalation.
3. **Everything runs as an async Postgres-queued worker** with an explicit per-document status machine (`extracted` / `ocr_applied` / `needs_review` / `failed`) so no upload is ever silently lost.

**Rough cost: ≈ $1.50–3.00 per 1,000 resumes** (typical mix, synchronous). With the Batch API for bulk/backfill imports: **≈ $0.70–1.50 per 1,000**. Even a pathological 100%-escalated-to-mid-tier batch stays ≤ ~$12 per 1,000. **Skip Apache Tika and `unstructured` for v1** — both are maintained but heavy (JVM / system deps) and add nothing for PDF+DOCX-centric ingestion; keep Tika in the back pocket as a sidecar if legacy-format volume justifies it later.

---

## 1. Constraints (from map.md)

- Python backend; **OpenAI API is the only paid external dependency** (no Affinda/Sovren-style parsing APIs).
- Postgres available (pgvector allowed).
- Ingestion is **upload + email-in only** (v1). Feeds tickets 05 (data model) and 09 (spec AI architecture).
- Persona: small companies; volume per tenant is tens-to-hundreds of resumes/month, not tens of thousands. Latency target: user uploads → sees parsed profile in well under a minute.

## 2. OSS extraction landscape — verified October 2026

All version/date data below pulled from PyPI / Apache project pages on 2026-10-20/21.

| Library | Version (date) | License | Maintenance verdict | Role in v1 |
|---|---|---|---|---|
| **pypdf** | 6.21.1 (2026-10-17) | BSD-3 | **Very active** (multiple releases/month, 3 maintainers, Py3.9–3.15, provenance-signed) | Fast pre-pass on PDFs: page count, encryption check, cheap text sanity check; fallback extractor |
| **pdfplumber** | 0.11.10 (2026-06-15) | MIT | **Maintained** (single primary maintainer + co-maintainer; slower cadence than pypdf but healthy; Py3.10–3.14; built on pdfminer.six) | **Primary PDF text extractor** — layout-aware `extract_text()`, word/line coordinates, handles multi-column better than pypdf |
| **python-docx** | 1.2.0 (2025-06-16) | MIT | **Stable** (slow release cadence is normal; Production/Stable; the canonical DOCX library) | **Primary DOCX extractor** (paragraphs + tables) |
| **OCRmyPDF** | 17.13.0 (2026-09-28) | MPL-2.0 | **Very active** (17.x line through 2026; Production/Stable; battle-tested, used by paperless-ngx) | OCR layer for scanned PDFs (wraps Tesseract; deskew/rotation; 100+ langs) |
| **Apache Tika** | 4.1.0 (latest; 3.3.3 maintenance line) | Apache-2.0 | **Active** (ASF project; 4.x requires Java 17+, ships zip distros not runnable jars) | **Not in v1.** JVM sidecar is an ops cost we don't need for PDF/DOCX/TXT/HTML. Revisit only if legacy `.doc`/`.rtf`/`.ppt` volume grows |
| **unstructured** | 0.27.32 (2026-10-20) | Apache-2.0 | **Very active**, but "4 - Beta" status; heavy system deps (libmagic, poppler, tesseract, **libreoffice**, pandoc); company steers toward its **paid** Transform API for quality | **Not in v1.** Its own OSS-vs-paid benchmark (OSS text accuracy 0.715 vs paid 0.878) signals where quality investment goes — and paid is off-limits by constraint. For resumes, the LLM layer absorbs extraction noise anyway |

Notes:

- **pdfplumber vs pypdf:** pdfplumber (pdfminer.six-based) gives better reading order on designed resumes (two-column, sidebars) at the cost of speed; pypdf is faster and more robust on weird/corrupt files. Using pypdf as pre-pass + pdfplumber as primary gets both. Neither does OCR (explicit non-goal in pdfplumber's docs) — hence OCRmyPDF.
- **PyMuPDF** is the speed king but **AGPL-3.0** — wrong license for a closed SaaS unless you buy a commercial license. Excluded.
- **Legacy `.doc` (binary Word):** no good pure-Python lib. Options: LibreOffice headless (`soffice --convert-to docx`, a system dep we already accept for OCRmyPDF? no — OCRmyPDF needs ghostscript+tesseract, not libreoffice) or Tika sidecar. **v1 decision: accept `.doc` from email-in (it will happen) but route to `needs_review` with a "please re-upload as PDF/DOCX" nudge, unless/until we add a LibreOffice conversion container.** Keep it a config flag, not a code path.
- **Images as resumes (jpg/png, e.g. photographed resumes):** skip local OCR entirely; route straight to the vision fallback (LLM reads page images natively). Cheaper than maintaining an image pipeline for a rare case.

## 3. OpenAI model landscape & pricing — October 2026

OpenAI's platform docs/pricing pages are auth-gated; lineup confirmed via openai.com (current models: **GPT-6.1 Sol, GPT-6 Astra, GPT-5.6, GPT-5.5**) and per-token prices cross-checked from the models.dev aggregator of official pricing (2026-10-20). **Re-verify exact prices at build time — OpenAI reprices often.** Naming as of Oct 2026: **Astra** = flagship, **standard GPT-x.y** = full-size, **Sol** = mid-tier, **Luna** = small/fast (the "mini/nano" successor line).

| Model | $/1M input | $/1M output | Cache read | Context | Fit for resume extraction |
|---|---|---|---|---|---|
| **gpt-5.6-luna** | **0.20** | **1.20** | 0.02 | 1M | ✅ **Recommended workhorse** — cheap, fast, 1M ctx, vision-capable |
| gpt-6-luna | 0.10 | 0.50 | 0.01 | 1M | ✅ Even cheaper (newest GPT-6 small tier) — A/B against 5.6-luna |
| gpt-5.4-nano | 0.20 | 1.25 | 0.02 | 400k | OK but previous-gen; no reason vs luna |
| gpt-6.1-sol / gpt-6-sol / gpt-5.6-terra | 2 | 10–12 | 0.1–0.4 | 1M | ✅ **Escalation tier** for hard/ambiguous docs |
| gpt-5.6 (standard) | 4 | 20 | 0.4 | 1M | Overkill for extraction |
| gpt-6-astra | 10 | 50 | 1 | 1M | ❌ Flagship — pointless here |
| text-embedding-3-small | 0.02 | — | — | 8k | For the later NL-search embedding (ticket 04) — ~$0.02 per 1,000 resumes, negligible |

Key API facts (verified via openai-python README, Oct 2026):

- **Responses API** is the primary interface; Chat Completions supported "indefinitely". Either supports structured outputs; use Responses with `text.format = json_schema, strict: true`.
- **Strict Structured Outputs** (guaranteed schema-constrained JSON) — available across the GPT-5/6 lineup. This is the load-bearing feature: no "please output JSON" prompt-begging, no repair loops for malformed JSON.
- **Prompt caching**: the fixed system prompt + schema (~600–800 tokens) is cache-read at $0.02/1M on luna — makes the per-call fixed cost nearly free at volume.
- **Vision input** (`input_image`, base64 or URL) works on current models → scanned-resume fallback needs no separate OCR model/API.
- **Batch API**: async, ~24h completion window, long-standing **50% discount** (couldn't re-verify the exact current % — docs are auth-gated; confirm at build time). Perfect for email-in backfills and bulk imports.
- SDK: `openai` ≥ current, Python 3.10+, automatic retries (default 2) on 429/5xx — rely on it plus jittered backoff; don't hand-roll retry logic.

## 4. Extraction schema (v1 sketch)

Design principles:

- **Faithful transcription, zero inference.** The prompt's prime directive: extract only what is present; never guess, normalize silently, or embellish. Every hallucinated employer name is an HR-user trust-killer and (per map) ranking/scoring is deferred partly for legal caution — keep extraction similarly conservative.
- **Dates are strings** (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`, or verbatim fragment), not parsed types — invalid/odd dates must not crash the pipeline; normalize in Python post-processing.
- **All fields optional except a `is_resume` + `confidence` pair** — the pipeline must degrade gracefully, not fail.
- **Arrays of small objects** for experiences/education; keep bullets verbatim (they feed summaries and search later).
- **Version the schema** (`schema_version`) and store `model` + `prompt_version` on every row — extraction quality is a moving target and we will want to re-parse cohorts later.

```jsonc
{
  "schema_version": 1,
  "is_resume": true,                  // routes non-resumes (cover letters, portfolios) out
  "confidence": 0.0,                  // model's self-assessed extraction confidence 0..1
  "needs_review": false,              // true if name/contact missing or confidence low
  "contact": {
    "full_name": null, "email": null, "phone": null,
    "location": null,                 // verbatim, not geocoded
    "links": [ {"type": "linkedin|github|website|other", "url": "..."} ]
  },
  "headline": null,                   // verbatim title under the name, if any
  "summary": null,                    // verbatim professional summary, if any
  "work_experience": [
    { "title": null, "company": null, "location": null,
      "start_date": null, "end_date": null, "current": false,
      "bullets": ["..."] }            // verbatim
  ],
  "education": [
    { "degree": null, "field": null, "institution": null,
      "start_date": null, "end_date": null } 
  ],
  "skills": [ "..." ],                // verbatim terms; normalization is a later, deliberate step (ticket 05)
  "certifications": [ {"name": null, "issuer": null, "date": null} ],
  "languages": [ {"language": null, "proficiency": null} ],
  "document_language": null,          // ISO code, feeds OCR + search later
  "extraction_notes": [ "..." ]       // model flags: truncation, illegible sections, conflicting dates
}
```

Store the full JSON in a Postgres `jsonb` column (ticket 05); the relational candidate fields (name/email/etc.) are copied up for querying, the JSON stays as source-of-truth for re-processing.

## 5. The concrete v1 pipeline

```
upload / email-in (ticket 03)
   │  store original bytes + SHA-256 (dedupe) + mime sniff (python-magic)
   ▼
[Postgres jobs table — status: pending]  ── worker picks up with SELECT … FOR UPDATE SKIP LOCKED
   │
   ├─ PDF ──► pypdf pre-pass ──► encrypted? try empty-password decrypt (pypdf[crypto]) → fail: needs_review
   │            │ ok
   │            ▼
   │        pdfplumber extract_text (layout-aware), per page:
   │            text < ~50 chars/page? ──► page flagged "scanned"
   │            │ any scanned pages?
   │            ├── yes ──► OCRmyPDF (deskew, rotate, -l eng+deu+fra) ──► re-extract
   │            │             still junk? ──► VISION FALLBACK: render pages (pdftoppm) →
   │            │             images into the same LLM call as input_image
   │            └── no ──► text ready
   │
   ├─ DOCX ──► python-docx (paragraphs + tables)
   │            near-empty? ──► fallback: unzip word/document.xml, strip <w:t> text nodes
   │            (covers text boxes python-docx misses); still empty → needs_review
   │
   ├─ .doc/.rtf/.odt ──► [config flag] LibreOffice headless → docx → above,
   │                      else needs_review + "please re-upload as PDF/DOCX"
   │
   ├─ image (jpg/png) ──► direct vision route (no local OCR)
   │
   └─ txt/html/md ──► trivial decode
   │
   ▼
normalize: NFKC unicode, collapse whitespace, strip email-forwarding/quoted
replies + signatures (email-in), truncate at ~24k chars (~6k tokens) with flag
   │
   ▼
LLM extraction — ONE call, Responses API, structured outputs (strict json_schema)
   model: gpt-5.6-luna (default) · low effort/temperature settings
   │
   ├─ pydantic validation ok ──► post-process in Python:
   │      email/phone regex pass, date normalization attempt, needs_review rules
   │      ──► persist candidate + jsonb + parse metadata ──► enqueue embedding (ticket 04)
   │
   └─ validation error / refusal / confidence < threshold
          ──► retry #1: same model, append validation errors to the prompt
          ──► retry #2: escalate to gpt-6.1-sol (or gpt-5.6-sol)
          ──► still bad ──► status: needs_review (never dropped, human sees doc + partial data)
```

Operational notes:

- **Idempotent + replayable:** keep the original file, the extracted raw text, and the raw model JSON with `model`/`prompt_version`/`schema_version`. Re-parse campaigns (new model, new schema) are a UPDATE + re-enqueue, not a migration crisis.
- **Worker:** one asyncio worker service (the repo stack is Python); Postgres-as-queue is sufficient at this scale — no Redis/Celery needed for v1 (feeds ticket 07 skeleton decision).
- **Model seam:** model IDs live in config (`RESUME_EXTRACT_MODEL`, `RESUME_EXTRACT_MODEL_ESCALATION`), never in code. Names and prices churn every few months (the Luna/Sol/Astra tiering is months old); the seam makes churn a config change.
- **Bulk path:** email-in backfills and "import folder" flows go through the **Batch API** (50% cheaper, 24h SLA) — same prompt, same schema, different transport. Interactive single uploads use sync calls for sub-minute UX.
- **Multilingual:** Tesseract lang packs + LLMs handle non-English resumes fine; `document_language` in the schema feeds later search/display. (Map notes EU-AI-Act awareness — a small-company EU customer will email German/French resumes.)

## 6. Failure-mode matrix

| # | Failure | Detection | Handling |
|---|---|---|---|
| 1 | Password-protected PDF | pypdf `is_encrypted` | empty-password decrypt attempt → else `needs_review` + reason |
| 2 | Corrupt/truncated PDF | pypdf strict parse raises | fallback: pdfplumber (pdfminer) → quarantine `needs_review` |
| 3 | Scanned PDF (no text layer) | < ~50 chars/page on ≥1 page | OCRmyPDF → re-extract → vision fallback → `needs_review` |
| 4 | Two-column / designed layouts | (inherent) | pdfplumber layout mode; LLM tolerant of imperfect ordering |
| 5 | DOCX text in text boxes | python-docx yields near-empty text | raw `document.xml` `<w:t>` strip fallback |
| 6 | Legacy `.doc`/RTF/ODT | mime sniff | config-gated LibreOffice convert, else `needs_review` + re-upload nudge |
| 7 | Photo-only resume (jpg/png) | mime sniff | direct vision route (image input to LLM) |
| 8 | Non-resume docs (cover letters, portfolios, certs) | `is_resume: false` from schema | route to attachment storage, don't create candidate; surface in UI |
| 9 | Absurdly long resume / CV-bomb | char/token count | truncate ~24k chars, set `extraction_notes: truncated` |
| 10 | Email-in clutter (quoted chains, signatures, disclaimers) | (email-in stage, ticket 03) | strip quoting/signature before extraction; attachment-first, body-second |
| 11 | Model hallucination | confidence + `needs_review` rules + spot-check evals | verbatim-only prompt policy; flag low confidence for human review screen (feeds 08) |
| 12 | Rate limits / transient 5xx | SDK exceptions | SDK built-in retries (2×) + our jittered backoff; Batch API for bulk |
| 13 | Duplicate submissions (re-forwarded email, double upload) | SHA-256 of file bytes | dedupe: point new submission at existing candidate, notify user |
| 14 | Weird encodings (old .txt, HTML entities) | decode errors / mime sniff | try utf-8 → latin-1 → chardet; strip HTML entities |

Every terminal state writes a status + reason; nothing is dropped silently. The `needs_review` bucket is a first-class UI surface (ticket 08), not an error log.

## 7. Cost model per 1,000 resumes

Assumptions: avg resume ≈ 1.5 pages → extracted text ≈ 1.2k tokens; system prompt + schema ≈ 700 tokens (mostly cache-read after the first call); output JSON ≈ 800 tokens. Sync path, cache hits amortized:

| Scenario | Math (per 1,000) | Total |
|---|---|---|
| **Typical mix: 90% gpt-5.6-luna, 10% escalated to gpt-6.1-sol** | 900×$0.00136 + 100×$0.012 | **≈ $2.40** |
| All-luna (best case, clean docs) | 1,000 × $0.00136 | ≈ $1.35 |
| Same typical mix via **Batch API (−50%)** | $2.40 × 0.5 | **≈ $1.20** |
| All escalated to mid-tier (pathological) | 1,000 × $0.012 | ≈ $12 |
| OCR: Tesseract path | CPU only | $0 |
| OCR: vision fallback on 10% of docs, 2 pages each | ~200 pages × ~1.5k image tokens × $0.20/1M | ≈ $0.06 |
| Embeddings for NL search (ticket 04, text-embedding-3-small) | 1,000 × 1.2k tokens × $0.02/1M | ≈ $0.02 |

**Headline for the spec: ≈ $1.50–3 per 1,000 resumes; budget $5/1,000 with headroom.** Per-resume: **$0.0015–0.003.** Even at 10× the volume assumptions this is noise against any plausible SaaS price — cost should not drive design tradeoffs here; reliability and the `needs_review` UX are what matter.

Latency: sync small-tier extraction runs ~1–3 s/resume; a 10-resume upload batch completes in seconds with a worker pool. Fine for the persona.

## 8. Deliberately deferred

- **Apache Tika sidecar** — the "parse anything" catch-all (1000+ formats). Revisit if real inbound data shows legacy formats beyond PDF/DOCX/images; a small tika-server container is a clean add-on behind the same jobs table.
- **`unstructured` OSS** — heavy deps, beta status, and its vendor's own benchmarks put OSS quality below the paid tier we've ruled out. The LLM layer already absorbs extraction noise.
- **PaddleOCR/RapidOCR/EasyOCR** — better than Tesseract on hard scans but pull big ML runtimes; the vision fallback covers the hard-scan tail more cheaply and with zero extra infra.
- **Skill taxonomy / normalization** (ESCO/O*NET mapping), salary extraction, and anything scoring-shaped — separate decisions (05 / later phases) with EU AI Act exposure.
- **Re-parse automation** — schema/model versioning is in v1, but automatic bulk re-extraction of existing candidates waits until there's a reason.

## 9. What this hands downstream

- **Ticket 05 (data model):** `candidates`, `resume_files` (bytes/sha256/mime), `parse_jobs` (status enum, model, prompt_version, schema_version, timings), `resume_extractions` (jsonb). Status enum: `pending | extracted | ocr_applied | vision_used | needs_review | failed | not_a_resume`.
- **Ticket 09 (spec):** the AI-architecture section gets: one-model-one-call extraction with strict structured outputs, model names behind config, retry-then-escalate ladder, Batch API for bulk, $-per-1k table, and the "OpenAI-only" vendor-seam statement.
- **Ticket 03 (email-in):** attachment extraction + signature/quote stripping happen at the email boundary, before this pipeline; .doc acceptance flag.
- **Ticket 08 (GUI):** the review/confirm parsed-data screen and the `needs_review` queue.

## Sources (accessed 2026-10-20/21)

- PyPI: pypdf 6.21.1, pdfplumber 0.11.10, python-docx 1.2.0, unstructured 0.27.32, ocrmypdf 17.13.0 (release history + metadata)
- tika.apache.org/download.html — Tika 4.1.0 / 3.3.3 maintenance line
- openai.com/api/pricing (model lineup nav: GPT-6.1 Sol, GPT-6 Astra, GPT-5.6, GPT-5.5); platform.openai.com docs auth-gated (403) — prices cross-checked via models.dev aggregator of official OpenAI pricing; re-verify before locking the spec
- github.com/openai/openai-python README — Responses API, structured outputs, vision input, retry behavior, Python 3.10+
