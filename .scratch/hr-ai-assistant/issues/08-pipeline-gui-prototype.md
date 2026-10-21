# 08 - Pipeline GUI prototype

Type: prototype
Status: resolved
Blocked by: 05, 06

## Question

What do the core screens actually feel like? Build a cheap, rough, throwaway prototype (React + shadcn/ui; static/mock data is fine) of: the pipeline board/list, candidate detail with a resume viewer plus the AI actions (summarize, natural-language search, compare, draft outreach), and the scheduling flow. React to it with the human, capture what lands and what misses, and link the prototype from this ticket's answer.

## Context

- Call the `prototype` skill. Cheap and rough is the point — fidelity only where the question demands it.
- GUI-first paradigm with AI embedded as actions (map Notes); domain entities and semantics are in `GLOSSARY.md` (pool-first Candidate/Role/Application, org-wide stage list with terminal Rejected/Withdrawn, Notes + Activity timeline, optional Owners/Unassigned).
- From 06: cover the Booking Page (slot pick/reschedule), the HR slot-proposing flow, and the draft-with-human-approval email pane alongside the pipeline board and resume viewer with AI actions.
- The screens validated here flow into the spec (09).

## Answer

**Artifact:** [`prototype/pipeline-ui-prototype.html`](../prototype/pipeline-ui-prototype.html) — single-file React+Tailwind (CDN), three structurally different variants of the pipeline home screen (A Board / B Table / C Master-detail), floating `?variant=` switcher, shared mock data and ticket-06 flows. Open in a browser; no build. (No git history in this repo, so the throwaway-branch capture rule degrades to the file itself living under `prototype/`, per map Notes.)

**Verdict (human):**
- **Winner: Variant A — Board.** Kanban columns per org-wide Stage is the home structure; stages are the primary way to see and move the pipeline.
- **Stolen from B:** the **NL-search bar with editable filter chips + semantic residual** (ticket 04's pattern) sits prominent in the header, and **candidate detail is a full page** with the editable extracted Profile block — superseding A's right-drawer as the canonical detail surface (a peek-drawer may still exist as a nicety; spec's call).
- **Ticket-06 surfaces validated as rendered:** draft-email pane (tone presets, editable body, "nothing sends without your click"), slot proposer (free/busy-checked 2–4 slots, booking link, email-only panel), and the Booking Page as the candidate sees it (timezone, cutoff, confirmed state). All flow into the spec as-is.
- **Nothing structurally missing** across the variants — the v1 surface is covered.

**Screen vocabulary for the spec (09):** pipeline board (stage columns, terminal Rejected collapsed-column treatment TBD in spec), full-page candidate detail (AI summary card, resume view, editable Profile, Notes & Activity timeline, AI action buttons: summarize/compare/draft-email/propose-slots), NL-chips search in the header, unassigned-owner visibility badges, saved-views row (B) NOT carried — the board replaces it.
