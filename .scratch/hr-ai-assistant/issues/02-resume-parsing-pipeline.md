# 02 - Resume parsing pipeline without third-party services

Type: research
Status: resolved

## Question

On a Python + OpenAI-only stack (no paid parsing APIs like Affinda/Sovren), what is the best v1 pipeline for turning uploaded/emailed resumes (PDF, DOCX, maybe scanned images) into structured candidate data? Evaluate OSS options (pypdf/pdfplumber, python-docx, Apache Tika, unstructured, OCR for scans) plus LLM-based structured extraction (extraction schema, model choice, cost per resume, fallbacks for weird formats). Recommend a concrete pipeline with failure modes handled, and a rough cost per 1,000 resumes.

## Context

- Ingestion is upload + email-in only (map Notes); Google Drive/other sources are not in v1.
- Feeds: the data-model decisions (05) and the spec's AI-architecture section (09).
- Findings go in `.scratch/hr-ai-assistant/research/`; link from the answer.

## Answer

**Recommended v1: OSS extraction → one strict structured-output OpenAI call.** Extract text locally with **pdfplumber** (primary, layout-aware) + **pypdf** (fast pre-pass/fallback) for PDFs, **python-docx** for DOCX (raw `document.xml` strip as text-box fallback), trivial paths for TXT/HTML. Detect scans via per-page text density → **OCRmyPDF/Tesseract** adds a text layer; only if OCR still fails, send page images as **vision input** to the LLM. Then a single **Responses API call with strict `json_schema` structured outputs** extracts a conservative, verbatim-only candidate schema (contact, work_experience[], education[], skills[], confidence, is_resume, needs_review) — **gpt-5.6-luna ($0.20/$1.20 per 1M)** as workhorse, one repair-retry, then escalate hard cases to **gpt-6.1-sol ($2/$10)**. Async Postgres-queued worker; every doc ends in an explicit status (`extracted / ocr_applied / needs_review / failed`), never dropped; SHA-256 dedupe; Batch API (−50%) for bulk imports. **Cost: ≈ $1.50–3 per 1,000 resumes (≈ $1.20 batched); budget $5/1,000.** Skip Tika (JVM sidecar) and `unstructured` (heavy beta deps; vendor's quality push is its paid API) in v1 — both are healthy projects, just wrong weight class for PDF+DOCX ingestion; keep Tika as a future sidecar if legacy formats show up.

Full findings, failure-mode matrix, schema sketch, and pricing table: [`research/02-resume-parsing-pipeline.md`](../research/02-resume-parsing-pipeline.md)
