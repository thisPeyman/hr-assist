# 12: Board home — Roles, Applications, Stages

**What to build:** The pipeline comes alive. HR creates a Role (Draft → Open) and optionally assigns it an Owner. Sourcing a Candidate onto the Role creates the one canonical Application per (Candidate, Role). The board home renders kanban columns per the org-wide Stage list (default Sourced → Screening → Interview → Offer → Hired, plus terminal Rejected / Withdrawn) with terminal Stages as collapsed columns at the board's right edge, expandable on click so the live pipeline keeps the width. Cards show name, headline/current title, and an Owner badge where Unassigned is visible. Dragging a card between Stages appends immutable Activity with optional free-text context; moving to Rejected offers — never requires — a preset reason plus free text. No stage ever moves automatically. Visual reference: the validated GUI prototype linked from spec §11.

**Blocked by:** 11 (Upload → parse → Candidate in the Talent Pool).

**Status:** resolved

Claimed by `implement/12-pipeline-board` (2026-10-31). API + isolated PostgreSQL
test seams; frontend static checks, no new browser/UI tests or live services.

- [x] Create a Role, move it Draft → Open, assign an optional Owner
- [x] Adding a Candidate to a Role yields exactly one canonical Application per (Candidate, Role); re-adding reuses it, never a twin
- [x] Drag between Stage columns; every move appends Activity with optional context; Rejected offers an optional preset reason
- [x] Terminal Stages render as collapsed columns at the right edge, expandable on click
- [x] Cards show name, headline/current title, Owner badge; Unassigned is visible and honest
- [x] No automatic stage transitions anywhere

## Answer

Implemented full backend and MUI/Emotion Persian RTL board/Role controls with
Candidate-detail sourcing. Board is authenticated home. Drag and accessible
keyboard/touch controls share an explicit stage confirmation dialog; context and
rejection reason never required. Rejected/Withdrawn use a collapsed physical-right
rail. Owner badges include honest Unassigned/inactive states and owner filtering.
Stage identity/kind is independent of display label; no automatic stage moves,
mail or inference of ownership.

Migration 0007 evolves existing Applications, retaining ids/data/legacy labels,
seeding org Stages and distinct legacy Roles without assuming same-title identity.
Canonical uniqueness plus shared identity/workflow locking handles concurrent
adds. Re-adding an ending reopens the same id. Same-Role Candidate Merge preserves
target stage/owner and unions notes/events, recording all retired source state.
Distinct-Role and automatic identity bridge Merge remain supported.

Verification: API/isolated PostgreSQL seams, full backend **199 passed** (including
S3 adapter after parent repaired shared locked dependencies); Ruff clean;
frontend build and **25 existing utility tests passed**, oxlint only four
pre-existing warnings. New tests cover concurrency, tenant/Member permissions,
active same-org owners, immutable Activity, stale moves, rename-safe kinds,
no automatic moves, Merge collisions, and legacy migration/backfill.

Resolved means implementation acceptance at the user-confirmed API/database
seams. **Browser acceptance is deferred, not passed**: drag interactions,
physical RTL placement, mobile/focus and visual acceptance still need browser/manual
verification. No live services, deployments or dev DB writes. Advanced endings
and admin pipeline editor remain tickets 25/26, not implemented here. Extension
and erasure warnings: [`docs/pipeline.md`](../../../docs/pipeline.md).
