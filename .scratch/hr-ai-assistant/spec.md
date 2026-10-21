# AI HR Assistant — v1 build-ready spec

Assembled from tickets 01–08 (see [References](#references)). Every decision below is locked; a build session should not need to re-open any of them. Working product name: "AI HR Assistant" (naming is out of scope).

---

## 1. What we're building

A **SaaS ATS — the system of record for hiring** — for small companies, with AI embedded as actions in a GUI-first product (not chat-first). v1 is beachheaded on **resume management + candidate pipeline + interview scheduling**.

Why we can win (positioning from [01]; pricing is positioning only — no billing in v1, from [07]):

1. **Flat pricing with unmetered AI** — incumbents meter AI via credit add-ons; the flat band starts at $157/mo. Undercut it, include everything.
2. **Compliance-forward "AI summarizes, human decides — no scoring"** — a marketed stance, not just an omission (EU AI Act / NYC LL144 exposure inverts competitors' scoring into a liability).
3. **Ashby-grade scheduling in the base product** — incumbents gate or outsource it.
4. **NL-first UX** — NL search with editable chips, precomputed summaries, first-class compare are the default interaction, not bolt-on buttons.
5. **Zero-sales time-to-value** — email-in ingestion: "forward a resume, watch it organize."

We concede: job-board distribution networks, sourcing databases, HRIS suites, agency portals.

## 2. Persona

**HR generalist at a 20–200 employee company, HR team of 1–5.** Wears every hat — recruiting is one of many jobs, not a profession. Not recruiters-at-scale, not enterprise. Implications: sub-minute feedback loops, no training budget, email is the natural medium, the GUI must carry the workflow (they aren't prompt engineers).

## 3. v1 scope and non-goals

**Stack constraints (locked):** Python backend, React + shadcn/ui frontend, Postgres (pgvector allowed). **Build-not-buy**: the OpenAI API is the only paid external dependency; free infra tiers acceptable. Standard cloud-AI privacy posture is acceptable for v1.

**Language & locale (locked):** The product is **Persian-first**. Every user-facing surface — GUI strings, the Booking Page, AI outputs (resume summaries, compare key-differences, outreach/invite/rejection drafts), and system email (invites, verification, resets, reminders) — is in **Persian (fa)** with **RTL layout end-to-end**. Dates render to users in **Jalali (Shamsi)**; storage and APIs stay Gregorian ISO 8601 — conversion happens at the presentation layer only. Resumes arrive **mixed Persian/English** (the norm in this market): extraction stays **verbatim, never translated** — values keep the resume's own language; only synthesized output is Persian. Persian text is normalized (ZWNJ, Arabic ی/ک → Persian forms) before indexing and at query time; lexical search runs on the normalized text with a `simple` FTS config (Postgres ships no Persian dictionary), and `pg_trgm` covers Persian names for typo tolerance. NL search accepts Persian and mixed fa/en queries; chips render Persian labels. Bilingual fa/en is out of scope for v1.

**In scope (v1):**

- Org signup, users, Admin/Member roles, in-app notifications
- Resume ingestion via **manual upload + email-in** (forward to an app address)
- Parse → structured, editable Profile; Talent Pool; Roles; Applications; org-wide stage pipeline
- AI actions: resume summaries, NL candidate search, candidate compare, draft outreach emails
- Interview scheduling: slot proposing, Booking Page, Google Calendar events, Meet links, reminders
- Email to candidates from the HR user's connected Gmail — always human-sent
- System email (invites, verification, resets) from the org's System Mailbox

**Non-goals (v1) — deliberately out:**

- **Candidate ranking/scoring/fit verdicts** — legal exposure; the compliance stance is the wedge
- Job-board distribution, sourcing databases, application portal/careers page, JD drafting
- Outlook/Microsoft calendar (the per-user OAuth seam is designed for it; post-v1)
- Reply-sync (candidate replies land in the HR user's normal inbox), round-robin pools, availability-rules engine
- Per-role pipelines (one org-wide pipeline), multi-Org membership per user, guest/external access
- Billing/payments entirely — v1 ships pilot-free with no plan schema
- Native mobile apps, SSO/SAML, enterprise compliance certifications
- Job-board & shared-inbox auto-scanning; chat-first UX

## 4. Product principles

1. **Human decides.** No automatic stage moves, no auto-send, no scoring. Every AI output is descriptive and grounded; every email needs a human click.
2. **Nothing dropped silently.** Every ingested document ends in an explicit status; `needs_review` is a first-class UI surface, not an error log.
3. **Corrections are never silently overwritten.** HR edits to the Profile win; re-extraction proposes diffs.
4. **AI failure degrades, never blocks.** Search falls back to lexical; summaries retry politely; the GUI works when OpenAI is down.
5. **Model choices live in config, prompts in versioned files.** OpenAI's lineup churns; none of it is load-bearing in code.

## 5. Domain model (from [05]; shared language in [`GLOSSARY.md`](../../GLOSSARY.md))

**Core entities — pool-first.**

- **Candidate** — a person + profile in the org-wide **Talent Pool**, role-less by default.
- **Role** — an open job; lifecycle Draft → Open → Paused ⇄ Open → Closed.
- **Application** — one candidacy joining a Candidate to a Role; holds the stage, its own Notes and Activity. **One canonical Application per (Candidate, Role)**; re-entering a closed/rejected candidacy reopens the same Application (logged in Activity), never a twin.

**Stages.** Attach to Applications. **One org-wide customizable pipeline** (default: Sourced → Screening → Interview → Offer → Hired, plus terminal **Rejected / Withdrawn**). Moving to Rejected *offers* (never requires) a preset reason + free text; any move may carry optional context.

**Merge & duplicates.** Email/phone match → **auto-Merge** (attach resume to existing Candidate, flag "new resume added"). Fuzzy name-only match → create the Candidate but prompt "possible duplicate — merge?" Merge unions applications and notes. SHA-256 dedupes identical files.

**Resume & Profile.** **Latest-resume-only**: newest resume file kept, older discarded (accepted audit trade for simplicity). Extraction populates the structured **Profile** (contact, skills, industries, work history with date ranges). Profile is HR-editable; a new resume re-extracts into empty fields only and surfaces changed fields as a **diff the HR person accepts or dismisses**.

**Notes & Activity.** **Notes** — human-written, editable, @Mention-capable, at Application and Candidate levels with aggregated views. **Activity** — append-only system events (stage changed, resume added, email drafted, AI summary regenerated, candidate actions from the Booking Page), split Application-level from Candidate-level.

**Collaboration.** Optional **Owner** per Role and per Application; "Unassigned" is first-class and filterable. @Mentions raise **in-app notifications only** (no email notifications in v1).

**Role closure.** Closing a Role asks what to do with live Applications: bulk-move to Rejected with optional shared reason, or leave untouched. Applications are never deleted by closure.

**Deletion.** Hard Delete (Admin-only) removes the person, resume, and Notes but **anonymizes Activity entries rather than deleting them** (GDPR erasure + audit continuity). A soft remove-from-pool also exists. No do-not-contact flag in v1 (a Note is the workaround).

## 6. Workflows

**W1 — Setup (Admin).** Sign up → Org created, creator = first Admin → connect the **System Mailbox** (org Gmail via OAuth) → invite Members (email invite only) → optionally edit the org-wide stage list and the reschedule cutoff (default 12h). The org's email-in address (`resumes+<companySlug>@jobs.<app-domain>`) is displayed for forwarding.

**W2 — Ingest.** HR forwards a resume email or uploads a file → parse pipeline runs → Merge/dedupe → new Candidate lands in the pool (or diff surfaces on an existing Profile) → summary precomputed, search doc embedded. A resume with no Role in mind simply sits in the pool.

**W3 — Pipeline.** Board home: Applications in columns per Stage; drag to move (logged as Activity with optional context/reason). HR creates a Role, opens it, assigns an Owner; Candidates get Applications (one per Role) as sourcing begins.

**W4 — Find & compare.** Type an NL query in the header ("backend engineer, fintech, 5+ years") → filters render as **editable chips**, results stream behind them → open full-page detail → **Compare** 2–4 candidates: deterministic table + LLM key-differences bullets.

**W5 — Outreach.** From candidate detail: **Draft email** (outreach / invite / rejection; tone presets, placeholders) grounded on Profile + Role + Notes → human edits and clicks **Send** → sends from the HR user's connected Gmail. Candidate replies land in that inbox (no reply-sync).

**W6 — Schedule.** From an Application: **propose 2–4 Slots** (checked against connected users' live Google free/busy) + panel of email-only Interviewers → interview-invite email links the **Booking Page** (tokenized, no login, candidate's timezone) → candidate books → Calendar event on the proposer's calendar with candidate + panel attendees, auto-Meet link, sibling Slots released → reminders 24h + 1h before → reschedule/cancel honored until the org cutoff → every candidate action notifies the HR owner in-app + writes Activity. **Cancel never moves the stage.**

**W7 — Endings.** Reject: optional preset reason, optional rejection email (drafted, human-sent). Hire: move to Hired, close the Role (bulk-reject or leave others untouched). Re-open later: same Application returns to a live stage.

## 7. Ingestion & resume parsing (from [02], [03])

### 7.1 Email-in

**Cloudflare Email Routing → thin Email Worker → HTTP POST of raw MIME to our Python webhook.** $0, unlimited inbound; MX on a dedicated subdomain.

- Address shape: `resumes+<companySlug>@jobs.<app-domain>`; one catch-all rule → one ~20-line Worker. The slug acts as a weak shared secret.
- Worker streams `message.raw` (octet-stream) to `POST /hooks/inbound-mail` with `X-Webhook-Secret`; **parallel forward to a backup dead-drop mailbox** (durability — Cloudflare won't retry our webhook); `setReject()` for non-matching recipients (proper SMTP bounce, not silence). No parsing in the Worker (free-plan 10 ms CPU).
- Python webhook: **durable-write first** (inbox row + raw .eml in object storage), return 200, then async: parse MIME, attachments-first/body-second, strip quoted chains + signatures, **ClamAV + type/size allowlist** (pdf/docx/txt/images); Persian subjects/bodies arrive as RFC 2047 encoded-words and must parse correctly. Idempotency key = `Message-ID` + recipient. Sender-MTA retries (~24–48h) cover provider outages.
- **Upgrade path** (trigger order): Cloudflare Queues + R2 for guaranteed delivery → Workers Paid $5/mo when parsing gets heavy → Amazon SES receiving (~$0.10/1k) or a paid inbound API only if needed. The raw-MIME contract makes that a one-record MX swap.

### 7.2 Upload

Same pipeline from W2, entered via the GUI; sync calls for sub-minute UX on single uploads.

### 7.3 Parse pipeline

Two layers: **OSS text extraction → one strict structured-output OpenAI call.**

1. **Extraction (local, free):** PDFs — pypdf pre-pass (encryption/corruption check) → **pdfplumber** (layout-aware); scanned pages detected by text density → **OCRmyPDF/Tesseract** (Persian + English language packs) → re-extract; still junk → **vision fallback** (page images into the LLM call). DOCX — python-docx, raw `document.xml` strip as text-box fallback. TXT/HTML trivial. Images → direct vision route. Legacy `.doc`/RTF — config-gated LibreOffice convert, else `needs_review` + "re-upload as PDF/DOCX" nudge.
2. **Structured extraction (the only paid step):** one **Responses API call, strict `json_schema` structured outputs** — **gpt-5.6-luna** workhorse, escalate hard cases to **gpt-6.1-sol**. Schema: conservative, verbatim-only — values keep the resume's own language, Persian or English, never translated (`contact`, `work_experience[]` with date ranges, `education[]`, `skills[]`, `is_resume`, `confidence`, `needs_review`, …); dates as strings normalized in Python; `schema_version` + `model` + `prompt_version` stored per row. Retry ladder: pydantic validation → one repair-retry same model → escalate → **`needs_review`, never dropped**.

Async worker on a **Postgres jobs table** (`SELECT … FOR UPDATE SKIP LOCKED`) — no Redis/Celery at this scale. Terminal statuses: `extracted | ocr_applied | vision_used | needs_review | failed | not_a_resume`. SHA-256 file dedupe. **Batch API (−50%)** for bulk/backfill imports. Original bytes, raw text, and raw model JSON are all kept — re-parse campaigns are UPDATE + re-enqueue.

**Cost: ≈ $1.50–3 per 1,000 resumes (≈ $1.20 batched); budget $5/1k.** Latency ~1–3s/resume sync.

## 8. AI features & architecture (from [04], [02])

Four actions, one shared prompt skeleton: **system (role/audience/tone) → grounding block (relevant structured fields + targeted excerpts, never the whole blob) → output contract (JSON schema or constrained prose) → guardrails** (every claim traces to provided data; unknown → "not stated in resume"; never infer or mention protected characteristics; descriptive, never evaluative). Prompts are versioned files in the repo with a ~20-input golden-set eval run on changes. **All synthesized output is Persian** — summaries, key-differences, drafts — even when the grounding resume is English; grounding data itself stays verbatim.

### 8.1 NL candidate search — hybrid, structured-first

One cheap LLM call parses the query into a **filter DSL**: `filters` (hard constraints: YOE thresholds, enums, negations, pipeline fields → compiled to SQL) + `semantic_query` (soft residual → pgvector cosine + Postgres FTS fused by **RRF**) + `constraint_softness` (for one-click "relax softest constraint" on empty results).

- **Numbers and negations never touch embeddings.** `years_experience_total` (and per-skill approximations) computed **in Python at ingestion** from role date ranges; the LLM only emits the threshold. Negations compile to SQL `NOT` and render as visible chips.
- **Persian & mixed queries.** The query-parse prompt handles Persian and mixed fa/en (including Persian numerals and YOE phrasing); all indexed text and queries pass Persian normalization (ZWNJ, Arabic ی/ک → Persian forms); lexical FTS runs on the normalized text with the `simple` config (Postgres ships no Persian dictionary); `pg_trgm` typo tolerance covers Persian names.
- **Index:** one **candidate-level embedding of a synthesized "search document"** (normalized fields + condensed resume text — not chunks; queries rank whole people), `tsvector` generated column + GIN, HNSW on the vector, B-tree tenant pre-filter with **exact vector scans at v1 scale** (HNSW iterative scans / partitioning = documented escalation). `pg_trgm` on names for typo tolerance.
- **Editable chips** are the GUI bridge: LLM mistranslation becomes a correction loop; chip edits re-run pure SQL. Parsed DSL cached per (tenant, query string).
- **Degradations:** parse fail → lexical-only fallback with a toast; vector fail → structured + lexical still run.
- **Safety:** the query-parse LLM sees only the user's query (never resume text — injection surface). Summary/compare/outreach treat resume content as untrusted data. **Protected-attribute filters are blocklisted at the code validation layer**, not just in prompts.
- **Latency/cost: p50 ≈ 1s, <$0.001/search.**

### 8.2 Resume summary

Runs once per resume version, **cached**. Schema'd output: headline; current title/employer; total years; key skills; notable employers/industries; education; languages; locations; **plus an "unclear or missing" list** so extraction gaps are visible. 120–180 words, non-evaluative.

### 8.3 Candidate compare (2–4)

**Two layers:** a deterministic side-by-side table rendered by app code from structured fields (numbers never transcribed by the LLM), + an LLM "key differences" block of 3–5 grounded, candidate-named bullets. **No winner verdict** — ends with "questions to ask," not recommendations.

### 8.4 Draft outreach

Three email types — first-contact outreach, interview invite (wraps the booking link), rejection — grounded on Profile + Role + Notes (+ match evidence when arriving from search). Output: subject + 80–150 word body, `[square-bracket placeholders]` for human-only facts, tone presets, one CTA. **Draft-only; nothing sends without a human click.**

### 8.5 Cost envelope

| Action | Cost |
|---|---|
| Parse+extract per 1k resumes | ≈ $1.50–3 (budget $5) |
| Per-candidate beyond parsing (search doc embed + cached summary) | < $0.01 |
| Search | < $0.001 |
| Outreach draft | ≈ $0.001–0.002 |
| Compare (capped at 4) | ≈ $0.002–0.01 |

## 9. Integrations

**Google — per-user OAuth, Calendar + Gmail-send in one consent** ([06]).

- Outbound candidate email sends from **the HR user's own connected Gmail** — deliverability rides on Google, the sender is a real human, replies land in their normal inbox. An unconnected user is prompted to connect before proposing slots or sending.
- Scheduling: free/busy checked only for **connected HR users**; events live on the **slot-proposer's calendar**; auto-created **Meet link**; attendees = candidate + panel.
- **Interviewers are never app users** — name + email only; they get plain invites and accept/decline in Google (not synced in v1).
- Reminders: automated candidate reminders at **24h and 1h** before, sent from the HR owner's Gmail; in-app morning-of reminder for the HR owner.
- **System Mailbox** ([07]): an org-designated Gmail/Workspace address connected by an Admin via the same OAuth flow; carries all system email (invites, verification, resets, future digests). One email integration, one deliverability story.
- **The Outlook seam** is exactly this boundary: who proposes slots, whose calendar hosts, whose Gmail sends.

**Email-in** — Cloudflare Email Routing per §7.1; detail in [research/03].

## 10. SaaS skeleton (from [07])

- **Tenancy:** Org + User + Membership; **one Org per User in v1**. Self-serve Org creation; creator = first Admin. One shared Postgres schema, `org_id` on every tenant-owned row, app-layer scoping **plus Postgres RLS** as belt-and-braces.
- **Auth:** self-rolled on a mature Python OSS library (e.g. fastapi-users): email + password with verification, argon2, cookie sessions, **optional TOTP 2FA** any user can enable. No hosted IdP.
- **Roles:** **Admin + Member** only. Admin: invite/deactivate Users, connect System Mailbox, edit org-wide pipeline, hard-delete Candidates. Members do all pipeline work. **Only Admins invite; removal is always deactivate** — attribution preserved, Google tokens revoked, name greyed out.
- **Org-level Activity stream** for admin actions (invites, mailbox connected, pipeline edited) — extends the Activity pattern.
- **Billing: deferred entirely.** v1 is pilot-free — no billing wired, no plan/pricing schema designed in. The flat-per-org unmetered-AI wedge stays positioning guidance until pilot evidence; pricing fog stays open on the map.
- Deferred with it: org self-serve data export (manual on request).

## 11. Screens (from [08]; visual reference: [`prototype/pipeline-ui-prototype.html`](prototype/pipeline-ui-prototype.html), Variant A + B's header/detail)

All screens are RTL with Persian strings and Jalali dates (§3 Language & locale).

1. **Board home** — kanban columns per org-wide Stage; drag to move. Terminal stages (**Rejected/Withdrawn**) render as **collapsed columns** at the board's right edge, expandable on click — live pipeline gets the width *(spec's call on 08's TBD)*. Cards: name, headline/current title, Owner badge (Unassigned visible).
2. **NL-chips search header** — prominent on the home screen; interpreted filters as editable chips; results stream behind them; "relax softest constraint" on empty. Covers the whole Talent Pool, including Candidates with no live Application.
3. **Full-page candidate detail** *(canonical detail surface — no peek-drawer in v1, spec's call)* — AI summary card; latest-resume view; **editable Profile** (with diff-accept on new resume); Notes + Activity timeline (application and candidate levels); applications list; AI action buttons: **summarize / compare / draft email / propose slots**.
4. **`needs_review` queue** — first-class surface for flagged parses (low confidence, missing name/contact, failed formats), showing doc + partial data.
5. **Draft-email pane** — tone presets, editable body, explicit "nothing sends without your click" send.
6. **Slot proposer** — free/busy-checked 2–4 Slots, email-only panel, booking link generation.
7. **Booking Page** (candidate-facing; the only one) — unguessable tokenized link, no login, candidate's browser timezone, pick/reschedule/cancel until cutoff, confirmed state.
8. **Role view** — lifecycle controls, live Applications, close-Role flow (bulk-reject or leave untouched).
9. **Admin/settings** — Users (invite/deactivate), org-wide pipeline editor, System Mailbox connect, email-in address, reschedule cutoff (default 12h, range 2–48h).

## 12. Persistence summary (collects the seams handed by 02/04/05/06/07)

`orgs`, `users`, `memberships` · `candidates` (+ `pg_trgm` name), `roles`, `applications`, stage config, `notes`, `activity` · `resume_files` (bytes/sha256/mime), `parse_jobs` (status enum, model, prompt_version, schema_version, timings), `resume_extractions` (jsonb) · `candidate_search_docs` (search_text, embedding + model, generated tsv, org_id) · `interviews` (round label, duration, Meet link), `slots`, `interviewers` (email-only), booking tokens · inbound mailbox rows (message-id, recipient, .eml ref) · per-user Google OAuth tokens; System Mailbox config · computed `years_experience_total` with `computed_at` on candidates.

## 13. Success criteria

1. **Time-to-value:** a new Org goes from signup to a parsed, AI-summarized Candidate in the pool **within 15 minutes**, no sales touch — including connecting email-in.
2. **Nothing dropped:** every submitted document ends in an explicit terminal status; `needs_review` is visible and worked in the UI, not a log.
3. **Costs at envelope:** parsing ≤ $5/1k resumes at typical mix; search p50 ≈ 1s and <$0.001/search.
4. **Compliance posture holds end-to-end:** zero scoring/ranking/fit verdicts anywhere in product or prompts; protected-attribute filters blocked at the validation layer; every candidate-facing email required an explicit human send; AI outputs surface "not stated" rather than inventing.
5. **Scheduling round-trip works as designed:** propose → book on the Booking Page → Calendar event with Meet link → 24h/1h reminders → reschedule/cancel honored until cutoff — and no stage ever moves automatically.
6. **Tenancy is airtight:** RLS enforced, app-layer scoping, deactivate-only user removal with attribution preserved.
7. **Pilot-ready:** an HR generalist runs the full loop — ingest → pipeline → search → compare → outreach → schedule → hire/reject — entirely in-app, in Persian (RTL, Jalali), without leaving for spreadsheets or a separate scheduler.

## 14. Later phases (sketch, not committed)

- **Event planning module** — generalizes the scheduling primitives the beachhead proves out (per-user calendar OAuth, free/busy checks, tokenized no-login RSVP pages, reminders, release-on-confirm) from interviews to events with invitee lists. Shape deliberately deferred until v1 shows which primitives generalized cleanly.
- **Repetitive-task copilot** — policy Q&A and drafting assistant for the same HR persona, grounded (RAG) over org-provided HR knowledge. Open question that gates design: **where does company HR knowledge live** (uploaded docs? wiki? notes?). Same prompt skeleton and guardrails; still descriptive, still human-sends.
- **Deferred seams** (each graduates to a ticket when its trigger fires): pricing/billing (after pilot evidence — flat per-org, unmetered AI as the hypothesis); Outlook (when v1 ships); JD drafting + careers page; reply-sync; multi-Org membership; org self-serve export; ranking/scoring (only as an explicit compliance-posture decision); Cloudflare → SES email-in upgrade (per §7.1 triggers).

## References

- Tickets: [`issues/01`–`08`](issues/) — competitive landscape, resume parsing, inbound email, NL search, domain model, candidate-facing, SaaS skeleton, GUI prototype.
- Research: [01](research/01-competitive-landscape.md) · [02](research/02-resume-parsing-pipeline.md) · [03](research/03-inbound-email-options.md) · [04](research/04-nl-search-architecture.md)
- Shared language: [`GLOSSARY.md`](../../GLOSSARY.md) · Map: [`map.md`](map.md) · Prototype: [`prototype/pipeline-ui-prototype.html`](prototype/pipeline-ui-prototype.html)
