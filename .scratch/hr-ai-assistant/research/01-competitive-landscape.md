# Research 01 — Competitive landscape: small-biz ATS + AI recruiting tools

Ticket: `.scratch/hr-ai-assistant/issues/01-competitive-landscape.md`
Researched: Oct 21, 2026.

**Method note:** web search was unavailable from this environment (403s), and several vendor sites block our egress IPs (Cloudflare/CloudFront). Data was gathered from live vendor pages where reachable (recruitee.com) and from Wayback Machine snapshots for the rest — all snapshots are from **Jul–Oct 2026** (dates cited per product). Teamtailor publishes no list price (quote-only); Recruitee's current pricing is demo-gated, so its last public numeric pricing (Mar 2025 snapshot) is cited. Findings below are vendor-published facts, not review-site folklore.

---

## 1. Pricing summary (entry paid tier, monthly)

| Product | Entry price (paid) | Pricing model | Self-serve trial | Annual discount / commitment |
|---|---|---|---|---|
| **Ashby** (Oct 2026) | **$400/mo** "All-In-One Foundations" (≤100 employees; interactive calculator by company size, 1–10 band = $400) | Flat by company size; Plus (101–1000) & Enterprise quote-based ("size, usage, commitment") | No — demo-gated | 10% annual discount; emerging-market pricing available |
| **Breezy HR** (Sep 2026) | Free forever (1 active job) → **Startup $157/mo** (annual) / $189 monthly → Growth $273/$329 → Business $439/$529 | Flat by tier; AI (Breezy Intelligence) is a **credit add-on** ($30 per 100k credits) | Yes — 14-day trial, incl. 100k AI credits | "2 months free" on annual |
| **Manatal** (Sep 2026) | **Professional $15/user/mo** (annual; $19 monthly) → Enterprise $35/$39 → Enterprise Plus $55/$59 → Custom | Per-recruiter-seat; unlimited hiring managers on all plans | Yes — free trial | ~20% annual delta |
| **Recruitee / Tellent** (Oct 2026 live; Mar 2025 last list prices) | Start **€270/mo monthly / €216 annual** (5 job slots, unlimited users); Grow €343/€274 (unlimited); 2026 relaunched as Start/Advance/Optimize — **demo-gated**, tiered by plan × employee count × billing period | Flat by tier + company size | Free trial; pricing requires demo | 20% annual discount; **1-year minimum contract** |
| **Teamtailor** (Aug 2026) | **Quote-only** ("Let us give you a quote"); unlimited jobs + unlimited users, 250+ features | Per-company quote (historically per-job-slot) | No — demo-gated | n/a |
| **Workable** (Oct 2026) — incumbent benchmark | **Standard $299/mo** (1–20 employees; price scales with headcount bands to 1000+) → Premier $599 → Enterprise $719; bundles ATS **+ HRIS** | Flat by tier × company size; AI agents metered via **AI credits** (3k free; 5k = $600, 10k = $1,000, 50k = $4,750) | Yes — 15-day trial | ~20% annual (bundle discount "up to 20%") |
| **Metaview** (Oct 2026) — AI-native entrant | Sourcing agent: Free (100 profiles) → **Pro $100/user/mo** (200 profiles/mo) → Max $300/user/mo (unlimited) → Enterprise custom | Per-user + usage-metered agents; layers **over** your existing ATS | Yes — free tier | n/a |

**Price floor anchors:** Manatal defines the per-seat floor ($15/user/mo); Breezy defines the flat-tier SMB band ($157–$439/mo); Ashby/Workable anchor the $299–$400+ "all-in-one" entry; Recruitee/Teamtailor hide prices behind sales. AI is increasingly **metered separately** (Workable credits, Breezy credits, Ashby AI credits 1,500/mo on Foundations, Recruitee Screening Assistant 100 credits/mo on Advance).

---

## 2. Feature matrix (beachhead scope: resume handling, pipeline, AI, scheduling)

| Capability | Ashby | Breezy HR | Manatal | Recruitee (Tellent) | Teamtailor | Workable |
|---|---|---|---|---|---|---|
| **Resume parsing → structured profile** | Yes — Quick Apply autofill; structured employment/education history; bulk import incl. **forwarded resume emails** | Yes — "world-class" parsing, 20+ languages, all parsed resumes searchable (free tier too) | Yes — CV parsing + indexing of skills/experience/education | Yes — CV parsing & search (Start tier) | Yes — CV parsing & search | Yes — automated resume parsing, auto-fill applications |
| **Resume summarization / AI read of candidate** | AI Candidate Assistant (chat over resume, notes, emails, transcripts); AI-assisted application review vs job criteria | Via Breezy Intelligence add-on (interaction summaries, resume auditing, candidate evaluation) | AI Copilot: automated candidate summarization, fit & gap analysis, compare & rank — **all plans** | AI Writer: candidate email drafting + feedback summaries (Start) | Co-pilot: summarize resumes and video interviews with one click | Screening Agent (AI credits) evaluates vs ideal candidate profile |
| **Candidate search** | Advanced/Boolean filters + **AI Candidate Search (natural language → filters)** + saved searches | Searchable parsed DB | Quick/advanced/Boolean + **AI semantic search with relevance scores** | CV parse & search | CV parsing and search | Talent CRM database search + Chrome sourcing extension |
| **Pipeline management** | Custom stages, interview plans per stage, automation per stage, bulk actions, auto-reject rules, confidential jobs | Customizable pipeline (Startup), multiple pipelines (Growth), stage-triggered automations, bulk actions | Unlimited custom pipelines (all plans), workflow automation (Enterprise+) | Pipeline templates + automations (Start), conditional workflow automations (Optimize) | Custom pipelines, automation triggers + "Smart Move" stage conditions | Custom hiring pipelines, automated actions |
| **AI matching / recommendations** | AI Talent Rediscovery (past candidates surfaced by signal type); AI Assisted Application Review; AI credits metered | Breezy Intelligence candidate evaluation (credit add-on) | AI Recommendations both directions (candidate↔job), custom weighting, **automatic AI scoring** — included | AI Matching Assistant (3 searches/mo on Advance; 65 on Optimize) | Co-pilot "suggest existing candidates" from talent bank; evaluate vs your criteria | Past-candidate resurfacing; Sourcing Agent (credits) |
| **Draft outreach / writing AI** | AI Outreach Personalization (sequence tokens), AI Content Assistant (JDs, emails, templates) | — (AI centered on evaluation/summaries) | AI job descriptions; copilot chat | AI Writer emails + feedback summaries + **AI job translations** | Co-pilot job ads/posts, brand-voice comms | Job Brief Agent (included); Engagement Agent (credits) |
| **Interview scheduling** | **Deepest in class**: self-serve booking links, availability links, visual scheduling, scheduling keywords, secondary calendars, buffers, interviewer limits, reminders, reschedule-reason capture, debrief scheduling; **Advanced Scheduling add-on**: AI auto-scheduler proposals, scheduling request queues, calendar holds, auto-replace declined interviewer, recruiting blocks, interviewer training automation | Interview self-scheduling (Startup+), Google/M365 email+calendar sync, video integrations (Zoom/Meet/Teams), one-way video | Gmail/Outlook & Teams calendar integration (no deep self-scheduling engine marketed) | Email & calendar sync (Start), candidate **self-scheduling** (Advance) | Interview scheduling **via Cronofy** (3rd-party) per Tellent's comparison page; interview kits | Self-scheduled interviews, two-way calendar sync (Gmail/365) |
| **Interview intelligence** | AI Notetaker (paid add-on): record/transcribe/summarize, AI interview summaries, feedback tokens | One-way video screening (Startup), video recording (Business) | **AI Interviewer add-on**: 24/7 async video screening interviews, multilingual, AI assessments | WhatsApp Hiring (AI chatbot) new add-on | Co-pilot meeting summaries, answer + suggest interview-kit questions | Video interviews add-on ($109/mo Standard) |
| **Job board distribution (we can't match)** | LinkedIn/Indeed/Google + hosted board | 50+ job boards even on free tier | LinkedIn/Indeed/Monster/ZipRecruiter organic integrations | Multi-job posting, auto-fill job board forms | Multi-board posting | 200+ boards, 400M+ candidate profiles |
| **Compliance posture** | GDPR rules, EEOC surveys, DEI analytics (some paid) | GDPR/EU data residency, EEOC/OFCCP (Startup+) | GDPR/CCPA/PDPA; markets "unbiased" AI assessments/scoring | GDPR automation, fairness/anonymization tools (Optimize) | GDPR, SOC2, ISO 27001 | GDPR automation, EEO/OFCCP/CCPA |
| **Open AI ecosystem** | **MCP server** + custom AI agents + Slack assistant | — | MCP server (Enterprise Plus) | AI statement published; API all plans | API + docs; Co-pilot privacy FAQ | API access |

---

## 3. AI-native entrants & frontier signals (2025–26)

- **Metaview** (Oct 2026): repositioned from interview notetaker to the **"Agentic Recruiting Platform"** — agents for sourcing, application review, screening, notes, reports, outreach, job posts, plus **"fillmore," an autonomous outbound recruiting coworker**. Raised an additional **$60M led by Insight Partners** in 2026. Per-user + usage pricing (see table). Integrates *over* existing ATSs — validates demand for AI layers but leaves the **system-of-record seat open at SMB**. Notable enterprise guardrails marketing: rules for what agents can't do, alerts for non-compliant behavior, **audit trail of AI reasoning**.
- **Workable Agent** (Oct 2026): incumbent answer to agents — Job Brief Agent included; Sourcing/Screening/Engagement agents metered by credits (evaluate = 1 credit, source = 2, chat = 10).
- **Manatal AI Interviewer** (Sep 2026): an incumbent shipping an always-on async AI video interviewer as an add-on — AI interviewing is going mainstream at SMB prices.
- **Mercor** (Oct 2026): the most-funded "AI hiring" startup ($10B valuation, Oct 2025, CNBC) **pivoted away from hiring** to AI-training data/evals ("organizing human intelligence to power the AI economy"). The AI-talent marketplace ≠ SMB ATS; not a direct competitor.
- **Tezi** (May 2026): AI-recruiter-agent startup **acquired by Headway** (mental-health) and exited recruiting entirely — evidence that standalone "AI recruiter agent" startups are consolidating/repurposing rather than winning the ATS seat.
- **Incumbent AI feature parity**: by 2026 *every* major SMB ATS ships AI summaries, AI writing, and some AI matching/screening (Ashby AI suite, Breezy Intelligence, Manatal Copilot, Tellent AI assistants, Teamtailor Co-pilot, Workable Agent). **"Has AI" is table stakes; the differentiators are where AI sits in the UX, how it's priced, and how it's governed.**
- Market consolidation: Recruitee is now **Tellent Recruitee** (modular HR platform with Tellent HR Manage/Grow); Breezy is part of **Learning Technologies Group**; the mid-market is being absorbed into suites.

---

## 4. Table stakes vs. differentiating (for an AI-first entrant, 20–200 employees)

**Table stakes — we must match these to be credible (everyone above has them):**
1. Resume parsing into a structured, searchable profile (multi-language at least EN; Breezy does 20+).
2. Customizable pipeline with stage-triggered automations (emails, tasks) and bulk actions.
3. Candidate database with saved/Boolean search.
4. Two-way email sync; at least basic calendar sync + some form of interview self-scheduling.
5. AI writing assist for candidate emails + job descriptions; AI resume/application summaries.
6. GDPR basics (consent capture, retention/deletion rules).
7. Multi-user collaboration: notes, mentions, evaluations, roles.

**Genuinely differentiating (and buildable under our constraints — OpenAI-only, build-not-buy, no job-board network):**

1. **Unmetered, included AI at a flat, honest price.** The 2026 incumbent pattern is AI nickel-and-diming: Workable credit packs ($600–$4,750), Ashby AI-credit tiers (1,500/mo cap on Foundations), Breezy $30/100k-credit add-on, Recruitee's 100 credits/mo Screening Assistant. "All AI actions included, no credit anxiety, no annual contract" undercuts the whole field psychologically — Manatal proves the $15–35/user/mo band works *with* AI included, but its UX is a traditional ATS with AI bolted on. This is the clearest pricing wedge: **flat per-company pricing below the $157–$400 flat-tier band, with AI unmetered**.
2. **Compliance-forward, human-decides AI (no scoring/ranking) as a marketed stance.** Manatal ships automatic AI scoring and "unbiased AI assessments"; Workable/Recruitee screen with agents; the EU AI Act's high-risk regime (our deferral decision) is a *selling point* to EU SMBs: AI summarizes, compares facts, and drafts — a human always decides and every AI output shows its sources. Nobody in the set markets "we deliberately don't score candidates." Metaview's audit-trail messaging shows enterprise buyers respond to AI-governance positioning.
3. **Scheduling depth at entry tier.** Ashby's best-in-class scheduling (booking links, interviewer pools/limits, buffers, holds, auto-replace declines, AI auto-scheduler) is gated behind Plus + a paid add-on; Teamtailor outsources to Cronofy; Breezy/Recruitee/Workable ship basic self-scheduling. A native Google Calendar scheduler with interviewer pools, buffers, holds, and one-click reschedule — **in the base product** — is build-not-buy territory and visibly better than the SMB tier of every incumbent above. (Directly feeds our scheduling ticket 06.)
4. **NL-first search and compare as primary UX, not a bolt-on.** Ashby's AI Candidate Search (prompt→filters) and Manatal's semantic search prove the capability but keep it adjacent to the filter-builder. Our v1 actions (NL candidate search, candidate compare, resume summaries on every profile) can make AI the *default* interaction model in a GUI-first product — summarization precomputed on every candidate, compare as a first-class view, NL as the search box. Differentiation is UX posture, not capability.
5. **Time-to-value: zero-sales onboarding.** Half the field is demo-gated with 1-year minimums (Recruitee, Teamtailor, Ashby). Email-in ingestion (forward a resume to an app address) + upload means a prospect can have a populated, AI-summarized pipeline in 15 minutes without a demo — only Breezy/Manatal/Workable offer self-serve trials, and none lead with "forward an email and watch it organize itself." That demo-able moment is the acquisition wedge that doesn't require a job-board network.

**What we cannot differentiate on (accept and ignore):** job-board distribution networks (50–200+ boards), 400M+ sourcing profile databases, employer-brand site builders, HRIS/onesboarding suites, agency portals. These are the incumbents' moat and explicitly outside our build.

---

## 5. Caveats & follow-ups

- Teamtailor list price: unobtainable (quote-only since at least the Aug 2026 snapshot). Third-party review sites peg historical per-slot pricing ~€85–100/mo, but no vendor-published 2026 figure exists — don't cite one in the spec without a source.
- Recruitee 2026 numeric pricing is demo-gated; €216–270/mo entry is the Mar 2025 last-published list (5 job slots, unlimited users). Directionally: entry ≈ €200–300/mo.
- Ashby's $400/mo is the calculator's 1–10 employee band; a 76–100 employee company pays more (calculator is interactive; exact band prices not captured).
- Workable's add-on prices ($89 texting, $109 video, $59 assessments, $39 performance on Standard) matter for bundle comparisons.
- Manatal's AI-scoring-included posture is worth a compliance watch: if EU AI Act enforcement makes scoring toxic for SMB buyers, Manatal's differentiator inverts into a liability — timing matters for our positioning section (ticket 09).
- Popp (popp.ai) was named as a candidate AI-native entrant but has no archive snapshot and is unverifiable from here; omitted.

## Sources (retrieved Oct 21, 2026)

- Ashby pricing + full feature matrix — `web.archive.org/web/20261009053932/https://www.ashbyhq.com/pricing`
- Breezy HR pricing — `web.archive.org/web/20260928061706/https://breezy.hr/pricing`
- Manatal pricing + plan comparison — `web.archive.org/web/20260907094917/https://www.manatal.com/pricing`
- Tellent Recruitee pricing (live, Oct 2026) — `recruitee.com/pricing`; last list prices — `web.archive.org/web/20250331235619/https://recruitee.com/pricing`
- Teamtailor pricing (quote-only) — `web.archive.org/web/20260829022010/https://www.teamtailor.com/en/pricing/`; AI Co-pilot — `web.archive.org/web/20260704014014/https://www.teamtailor.com/en/ai-recruiting-software/`; Cronofy/automation detail — `web.archive.org/web/20261003032230/https://recruitee.com/compare/tellent-recruitee-vs-teamtailor`
- Workable pricing + AI credits — `web.archive.org/web/20261020075005/https://www.workable.com/pricing`
- Metaview platform + pricing — `web.archive.org/web/20261011011548/https://metaview.ai/`, `web.archive.org/web/20261013132337/https://www.metaview.ai/pricing`
- Mercor pivot — `web.archive.org/web/20261005013432/https://www.mercor.com/` (links to CNBC Oct 27, 2025, $10B valuation)
- Tezi acquisition by Headway — `web.archive.org/web/20260515103819/https://tezi.ai/`
