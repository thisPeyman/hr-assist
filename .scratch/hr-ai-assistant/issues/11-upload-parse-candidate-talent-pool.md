# 11: Upload → parse → Candidate in the Talent Pool

**What to build:** The core tracer bullet. An HR Member uploads a resume file (PDF, DOCX, or TXT) in the GUI and within roughly a minute a new Candidate appears in the Talent Pool with a structured, HR-editable-ready Profile: contact, skills, industries, work history with date ranges. Under the hood: OSS text extraction (pypdf pre-pass for encryption/corruption → pdfplumber for PDFs; python-docx for DOCX; TXT trivial) feeding one strict structured-output OpenAI call — the workhorse model from config, prompts as versioned files. The retry ladder is pydantic validation → one repair-retry on the same model → escalate → `needs_review`; every submitted document ends in an explicit terminal status, nothing dropped silently. Async work runs on a Postgres jobs table (`SELECT … FOR UPDATE SKIP LOCKED`) — no Redis/Celery — with a sync path for sub-minute UX on single uploads. Identical files dedupe by SHA-256. Original bytes, raw text, and raw model JSON are all kept; model, prompt_version, schema_version stored per row. The Talent Pool list and a minimal candidate detail screen render the Profile. Resumes arrive mixed Persian/English — extraction keeps values verbatim in the resume's own language, never translated — and work-history date ranges display in Jalali. (Spec §3 Language & locale, §5, §7.2–7.3, §11 screens 1–3 minus the board.)

**Blocked by:** 10 (Org & auth walking skeleton).

**Status:** ready-for-agent

- [ ] Upload PDF/DOCX/TXT → Candidate in the Talent Pool with structured Profile, sub-minute on the sync path
- [ ] Every submitted document reaches an explicit terminal status (`extracted` / `needs_review` / `failed` / `not_a_resume`) — nothing dropped silently
- [ ] Retry ladder holds: validation fail → one repair-retry → escalate → `needs_review`, never a drop
- [ ] Mixed Persian/English resumes extract correctly; values stay verbatim in the resume's own language
- [ ] Work-history date ranges display in Jalali on candidate detail
- [ ] Identical file (same SHA-256) does not create a duplicate Candidate
- [ ] Jobs run on the Postgres jobs table with SKIP LOCKED; no Redis/Celery
- [ ] Model name lives in config; prompts in versioned files; `model` + `prompt_version` + `schema_version` stored per row; original bytes, raw text, and raw model JSON retained
- [ ] Talent Pool list and candidate detail render the Profile; tests across schema, API, and UI
