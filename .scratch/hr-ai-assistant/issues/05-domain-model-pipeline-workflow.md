# 05 - Domain model & pipeline workflow

Type: grilling
Status: resolved

## Question

What are the core domain entities and workflow of the hiring pipeline? Settle: the Role ↔ Candidate ↔ Application model; default and custom stages; how resumes attach to candidates (one candidate, many applications?); notes/activity trail; and multi-user collaboration in v1 (comments, assignments, @mentions?) plus notifications. Output: agreed glossary terms written to `GLOSSARY.md` at the repo root.

## Context

- Call the `grilling` and `domain-modeling` skills. Use the standard question box for every question.
- Constraints: we are the ATS (system of record); small-company persona; small HR team collaborating.
- The GUI prototype (08) blocks on this. Informed by competitive research (01) but not blocked by it.
- Seam from 04: the model must carry normalized skills/industries and per-role date ranges (YOE is computed from these at ingestion), since search compiles hard constraints straight to SQL over these fields.

## Answer

All decisions below are live in `GLOSSARY.md` (repo root) as shared language.

**Core entities — pool-first.** Three first-class entities: **Candidate** (person + profile, living in an org-wide **Talent Pool**, role-less by default), **Role** (open job), **Application** (the candidacy joining one Candidate to one Role; holds the stage, its own notes and activity). A resume arriving with no role in mind simply lands in the pool.

**Stages.** Stages attach to **Applications**. One **org-wide customizable pipeline** shared by all Roles in v1 (default: Sourced → Screening → Interview → Offer → Hired, plus terminal Rejected / Withdrawn). No per-role pipelines in v1. **Rejected/Withdrawn are stages flagged terminal; there is one canonical Application per (Candidate, Role)** — re-entering the same role moves the same Application back to a live stage, logged in Activity; no twin Applications. Moving to Rejected offers (never requires) a preset reason plus free text; any move may carry optional context.

**Duplicates.** Email/phone match → auto-Merge: attach the resume to the existing Candidate and flag "new resume added". Fuzzy name-only match → create the Candidate but prompt "possible duplicate — merge?" Merge keeps the union of applications and notes.

**Resume & profile.** Latest-resume-only: the newest resume file is kept, older files discarded (deliberate deviation from the recommended versioned-documents — accepted audit-trade for simplicity). Extraction populates the structured **Profile** (contact, skills, industries, work history with date ranges — the 04 seam). Profile fields are HR-editable; when a new resume arrives, re-extraction fills only empty fields and surfaces changed fields as a diff the HR person accepts or dismisses — corrections are never silently overwritten.

**Notes & Activity.** Two entities, one aggregated timeline per Application (and per pool Candidate): **Notes** are human-written, editable, @Mention-capable; **Activity** is an append-only system-event log (stage changed, resume added, email drafted, AI summary regenerated). Notes attach at both levels (Application and Candidate) with aggregated cross-application views; Activity splits Application events from Candidate events (merges, profile edits).

**Role lifecycle.** Draft → Open → Paused ⇄ Open → Closed. Closing a Role asks what to do with live Applications: bulk-move to Rejected with an optional shared reason, or leave untouched. Applications are never deleted by Role closure.

**Collaboration v1.** Optional **Owner** per Role and per Application; "Unassigned" is a first-class, filterable state. @Mentions raise in-app notifications only (no email notifications in v1 — outbound email rides on ticket 06). No guest/external access.

**Small rulings.** No do-not-contact flag in v1 (a Note is the workaround). Deletion: hard Delete (org-admin only) removes the person, latest resume, and notes but **anonymizes Activity entries rather than deleting them** (GDPR erasure + audit continuity); a soft remove-from-pool also exists.

**Seams handed forward.** 06: the Interview/booking entity and candidate-facing vocabulary extend this glossary; note that in-app-only notifications make an outbound-email path optional for later. 07: org-admin powers now include hard-delete and org-wide pipeline editing — fold into the roles/permissions decision. 09: everything above is spec-ready.
