# 12: Board home — Roles, Applications, Stages

**What to build:** The pipeline comes alive. HR creates a Role (Draft → Open) and optionally assigns it an Owner. Sourcing a Candidate onto the Role creates the one canonical Application per (Candidate, Role). The board home renders kanban columns per the org-wide Stage list (default Sourced → Screening → Interview → Offer → Hired, plus terminal Rejected / Withdrawn) with terminal Stages as collapsed columns at the board's right edge, expandable on click so the live pipeline keeps the width. Cards show name, headline/current title, and an Owner badge where Unassigned is visible. Dragging a card between Stages appends immutable Activity with optional free-text context; moving to Rejected offers — never requires — a preset reason plus free text. No stage ever moves automatically. Visual reference: the validated GUI prototype linked from spec §11.

**Blocked by:** 11 (Upload → parse → Candidate in the Talent Pool).

**Status:** ready-for-agent

- [ ] Create a Role, move it Draft → Open, assign an optional Owner
- [ ] Adding a Candidate to a Role yields exactly one canonical Application per (Candidate, Role); re-adding reuses it, never a twin
- [ ] Drag between Stage columns; every move appends Activity with optional context; Rejected offers an optional preset reason
- [ ] Terminal Stages render as collapsed columns at the right edge, expandable on click
- [ ] Cards show name, headline/current title, Owner badge; Unassigned is visible and honest
- [ ] No automatic stage transitions anywhere
