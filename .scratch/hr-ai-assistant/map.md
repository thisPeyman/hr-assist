# Wayfinder map: AI HR Assistant

Label: wayfinder:map

## Destination

A **build-ready spec** at `.scratch/hr-ai-assistant/spec.md` for v1 of a SaaS AI HR assistant — beachheaded on **resume management + candidate pipeline + interview scheduling** for HR generalists at small companies (20–200 employees, HR team of 1–5) — plus a short sketch of later phases (event planning, repetitive-task copilot). Done when every decision needed to start building is locked and written down, ready to hand to a build session.

## Notes

- **Product shape**: SaaS, multi-company. **We are the system-of-record for hiring** (the ATS), not a layer over existing ATSs. **GUI-first with AI embedded** as actions; not chat-first.
- **Persona**: HR generalist at a small company, wears every hat. Not recruiters-at-scale, not enterprise.
- **v1 AI actions**: resume summaries, natural-language candidate search, candidate compare, draft outreach emails. **Deferred: ranking/scoring** (EU AI Act / NYC LL144 high-risk exposure).
- **Ingestion (v1)**: manual upload + email-in (forward to an app address). No job-board or shared-inbox auto-scanning.
- **Calendar (v1)**: Google Calendar only, with a seam for Outlook later.
- **Stack constraints**: Python backend (AI ecosystem), React + Material UI/Emotion frontend (2026-10-31 continuation decision supersedes shadcn/ui), Postgres (pgvector allowed). **Build-not-buy**: the only external paid dependency is the OpenAI API. Standard cloud-AI privacy posture is acceptable for now.
- **Skills**: decision tickets → call `grilling` + `domain-modeling`; GUI ticket → call `prototype`; research tickets resolve via subagents.
- **Domain glossary**: lives at `GLOSSARY.md` at the repo root (repo convention overrides the domain-modeling skill's `CONTEXT.md` naming). Glossary only — no implementation detail.
- **Tracker**: local markdown, see `docs/agents/issue-tracker.md` — `Type:`/`Status:`/`Blocked by:` lines, `## Answer` on resolve, frontier scan in `.scratch/hr-ai-assistant/issues/`.
- **Research findings**: repo has no git history/remote, so the throwaway `research/<name>` branch convention is replaced: findings live under `.scratch/hr-ai-assistant/research/` and are linked from their tickets.

## Decisions so far

<!-- one line per closed ticket: gist + link. Empty at charting. -->

- [02 - Resume parsing pipeline](issues/02-resume-parsing-pipeline.md): OSS text extraction (pdfplumber/pypdf/python-docx + OCR fallback) feeding one strict structured-output OpenAI call (gpt-5.6-luna, escalate to gpt-6.1-sol); every doc ends in an explicit status; ≈ $1.50–3 per 1,000 resumes. Detail: `research/02-resume-parsing-pipeline.md`
- [04 - NL search architecture](issues/04-nl-search-architecture.md): hybrid search, structured-first — one cheap LLM call → filter DSL (hard constraints → SQL) + semantic residual (pgvector cosine + FTS fused by RRF); candidate-level "search document" embeddings; YOE computed at ingestion, never by embeddings; filters render as editable GUI chips; ~1s p50, <$0.001/search. Detail: `research/04-nl-search-architecture.md`
- [03 - Inbound email options](issues/03-inbound-email-options.md): Cloudflare Email Routing → thin Worker POSTs raw MIME to our Python webhook — $0, unlimited inbound; catch-all `resumes+<companySlug>@` routing, backup dead-drop forward instead of retries, MIME/attachment parsing and ClamAV in Python; upgrade path stays on Cloudflare then SES (one-record MX swap). Detail: `research/03-inbound-email-options.md`
- [01 - Competitive landscape](issues/01-competitive-landscape.md): incumbents all ship the same AI trio but meter it via credit add-ons; per-seat floor $15/user (Manatal) vs flat band $157–439/mo; AI-native entrants failed to take the system-of-record seat. Our wedges: flat sub-$157 pricing with unmetered AI, compliance-forward "no scoring — human decides" stance, Ashby-grade scheduling in base, NL-first UX, zero-sales email-in onboarding. Concede job-board networks/HRIS suites. Detail: `research/01-competitive-landscape.md`
- [05 - Domain model & pipeline workflow](issues/05-domain-model-pipeline-workflow.md): pool-first trio — Candidate (org-wide Talent Pool) + Role + Application (one canonical per Candidate×Role, reopenable); one org-wide custom stage list; auto-Merge on email/phone, prompt on fuzzy; latest-resume-only with editable Profile and diff-accept re-extraction; Notes (editable) + Activity (append-only) at both levels; optional Owners, @Mentions, in-app-only notifications; hard Delete anonymizes Activity. Glossary: `GLOSSARY.md`
- [06 - Candidate-facing surfaces](issues/06-candidate-facing-surfaces.md): email sends from the HR user's connected Gmail, always human-approved (outreach/invite/rejection drafts); HR proposes 2–4 concrete Slots, candidate picks on a tokenized Booking Page (the only candidate-visible surface; no portal, no status page); email-only Interviewer panels, auto Meet links; 24h+1h candidate reminders; reschedule cutoff per-org (default 12h); stage moves never automatic; per-user Google OAuth (Calendar + Gmail send). Glossary extended: Interview, Slot, Interviewer, Booking Page
- [07 - SaaS skeleton](issues/07-saas-skeleton.md): one Org per User (self-serve creation, creator = first Admin); shared schema + org_id + Postgres RLS; self-rolled auth on a Python OSS lib (password + verification, optional TOTP); org-level Activity stream for admin actions; Admin + Member only (invite = Admin-only; removal = deactivate-only, attribution preserved); System Mailbox (org-designated Gmail via OAuth) carries all system email; billing and pricing model deferred entirely — v1 is pilot-free with no plan schema. Glossary extended: Org, Admin, Member, System Mailbox
- [08 - Pipeline GUI prototype](issues/08-pipeline-gui-prototype.md): Board wins — kanban home per org-wide Stage, with B's full-page candidate detail + editable Profile and 04's NL-chips search bar stolen in; ticket-06 flows (draft email with human-send, slot proposer, Booking Page) validated as rendered; nothing structurally missing. Artifact: `prototype/pipeline-ui-prototype.html`
- [09 - Assemble the build-ready spec](issues/09-assemble-build-ready-spec.md): **destination reached** — human-approved build-ready spec at `spec.md`: v1 scope/non-goals, persona, workflows, domain model, candidate-facing behavior, AI features + architectures, integrations, SaaS skeleton, screens, success criteria, later-phases sketch. Spec's-call rulings: terminal stages = collapsed board columns; no peek-drawer (full-page detail only). **The map is done.**
- [11 - Upload → parse → Candidate in the Talent Pool](issues/11-upload-parse-candidate-talent-pool.md): the core tracer bullet, implemented — two-layer parse (OSS extraction → one strict structured-output OpenAI call, models in config, prompt v1 file), retry ladder ending in explicit terminal statuses (`extracted`/`needs_review`/`failed`/`not_a_resume`), Postgres jobs table with two-phase `FOR UPDATE SKIP LOCKED` claims under RLS (SELECT-only queue-visibility carve-out on pending rows), sync inline path for single uploads + lifespan drain loop, SHA-256 dedupe via `ON CONFLICT DO NOTHING`, bytes/raw-text/raw-JSON retained with model+prompt_version+schema_version per row, Talent Pool + candidate detail rendering verbatim values with Jalali work-history ranges; `[0-9]` not `\d` in date regexes (Persian digits!). Commits `e8b44a9`/`a3b7b07`/`573c8bf`

- [16 - Email-in ingestion](issues/16-email-in-ingestion.md): authenticated durable local/S3 MIME receipts, duplicate protection, async MIME processing, scanner quarantine/rescan, Cloudflare Worker and local mock/replay tooling. No real domain configured per user instruction.
- [20 - Needs-review queue](issues/20-needs-review-queue.md): tenant-scoped review/history, original downloads and safe image previews, editable partial Profiles, accept/dismiss, provenance retention and replay protection; browser verified on desktop/mobile.
- [21 - Parse hardening](issues/21-parse-hardening-ocr-vision.md): fas+eng OCR command route, vision fallback, gated LibreOffice conversion and explicit statuses; external executables/model mocked in integration checks, real rendering tested. Runtime prerequisites: `docs/resume-ingestion.md`.

- [13 - Editable profile and merge](issues/13-editable-profile-diff-merge.md): implemented candidate workspace, normalized matching, protected corrections, diff decisions, latest-only retention and merge transfer under tenant isolation.
- [14 - Cached AI summary](issues/14-cached-ai-resume-summary.md): cache, precomputation, regeneration, guardrails and 20-case offline evaluation implemented. Groq access recovered on retest; a real 173-word Persian summary was persisted. Full live golden evaluation remains pending.
- [29 - Review regressions](issues/29-review-regressions.md): repair the current MUI continuation's missing review/settings routes; preserve Candidate/Activity on resume deletion; reuse identity/reconciliation/version/summary paths for human ingestion; explicit stale-safe corrections and retired proposals; Jalali diff/certificate presentation. API/Postgres regressions and static frontend validation; browser/live acceptance deferred.

## Not yet specified

- **Pricing & billing model** — deferred by explicit decision at 07: v1 is pilot-free with no billing wired and no plan schema. The 01 wedge (flat per-org, unmetered AI) stays as positioning guidance; sharpen with pilot evidence, then a fresh ticket.
- **Org self-serve data export** (candidates/roles/applications as JSON/CSV) — deferred at 07; handled manually on request until it becomes a ticket.
- **Later phase: event planning module** — the event workflow shape depends on how scheduling/calendar generalizes once the beachhead is specified.
- **Later phase: repetitive-task copilot** — policy Q&A / drafting assistant; the open question is its knowledge source (where does company HR knowledge live?) and what the spec's sketch should cover.
- **Job posting / publishing** — job-board distribution out of scope; application portal / careers page ruled out of v1 (06). Remaining: JD drafting + careers page as later-phase sketch material for 09.
- **Candidate ranking/scoring** — deferred out of v1 for legal exposure; a future decision on whether/how to add it with a compliance posture.
- **Outlook/Microsoft calendar support** — post-v1; the seam is now defined by 06 (per-user OAuth boundary: who proposes slots, whose calendar hosts, whose Gmail sends). Graduates to a ticket only when v1 ships.

## Out of scope

- **Native mobile apps** — v1 is a web GUI; native mobile is ruled out of this effort.
- **AI layer over existing ATSs** (Greenhouse/BambooHR integration mode) — ruled out at charting: we are the ATS.
- **Enterprise features** — SSO/SAML, compliance certifications, enterprise persona; the persona is small-company HR.
- **Job-board & shared-inbox auto-ingestion** — ruled out of v1 ingestion at charting (upload + email-in only).
