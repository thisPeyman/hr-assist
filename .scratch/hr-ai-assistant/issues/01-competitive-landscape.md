# 01 - Competitive landscape: small-biz ATS + AI recruiting tools

Type: research
Status: resolved

## Question

What do existing small-business ATS / AI recruiting products (e.g. Ashby, Breezy HR, Manatal, Recruitee, Teamtailor, plus any 2025–26 AI-native entrants) already offer around resume handling, pipeline management, AI features, and scheduling — and what do they charge? What is table stakes vs. genuinely differentiating for an AI-first entrant aimed at HR generalists at 20–200 person companies? Produce: a feature matrix, a pricing summary, and 3–5 differentiators our spec could lean on.

## Context

- Stack constraints in map Notes (OpenAI-only, build-not-buy): what we can't match (e.g. job-board distribution networks) shouldn't anchor our differentiation.
- Feeds: the SaaS-skeleton/billing decisions (07) and the spec's positioning section (09).
- Findings go in `.scratch/hr-ai-assistant/research/`; link from the answer.

## Answer

**Full findings:** [research/01-competitive-landscape.md](../research/01-competitive-landscape.md) (feature matrix, pricing table, per-product detail, sources — all from Jul–Oct 2026 vendor pages/snapshots).

**Summary:** The SMB ATS market has bifurcated into a per-seat floor (Manatal $15/user/mo, AI included) and a flat-tier band (Breezy $157–439/mo, Workable $299/mo, Recruitee ~€216–270/mo entry, Ashby from $400/mo, Teamtailor quote-only) — and by 2026 every incumbent ships the same AI trio (resume summaries, AI writing, some matching/screening), usually **metered via credit add-ons** (Workable, Ashby, Breezy, Recruitee). AI-native entrants didn't take the system-of-record seat: Metaview layers agents over existing ATSs ($100–300/user/mo), while Mercor pivoted to AI-data and Tezi was acquired out of recruiting. Table stakes for us: parsing → structured searchable profiles, custom pipelines with stage automations, email/calendar sync, self-scheduling, AI email/JD drafting, GDPR basics. Five defensible differentiators within our constraints: (1) flat, sub-$157 pricing with AI unmetered (anti-credit-meterng wedge); (2) compliance-forward "AI summarizes, human decides — no scoring" stance (inverts Manatal/Workable's scoring into an EU AI Act liability); (3) Ashby-grade scheduling depth in the base product (incumbents gate it or outsource to Cronofy); (4) NL-first search/compare/precomputed summaries as the default UX rather than bolt-on AI buttons; (5) zero-sales time-to-value via email-in ingestion ("forward a resume, watch it organize") against a demo-gated, 1-year-contract field. Don't compete on job-board networks, sourcing databases, or HRIS suites — that's the incumbent moat and outside build-not-buy.
