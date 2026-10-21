# 25: Endings — reject, hire, close the Role

**What to build:** Candidacies end cleanly and reopen cleanly. Rejecting offers — never requires — a preset reason plus free text, and optionally drafts a rejection email (human-sent, per ticket 19's pane). Re-entering a closed/rejected candidacy reopens the same canonical Application, logged in Activity — never a twin. Hiring moves the Application to Hired and prompts closing the Role: the close flow asks what to do with live Applications — bulk-move to Rejected with an optional shared reason, or leave them untouched — and closure never deletes Applications. The Role view screen shows lifecycle controls (Draft → Open → Paused ⇄ Open → Closed) and its live Applications. (Spec §5 Role closure, §6 W7, §11 screen 8.)

**Blocked by:** 12 (board — Roles, Applications, Stages), 19 (draft-email pane for the optional rejection email).

**Status:** ready-for-agent

- [ ] Reject flow: optional preset reason + free text; optional drafted rejection email, human-sent only
- [ ] Re-entering a closed/rejected (Candidate, Role) pair reopens the same Application, logged in Activity
- [ ] Close-Role flow offers bulk-reject (optional shared reason) or leave-untouched; closure never deletes Applications
- [ ] Role view shows lifecycle controls and live Applications; Paused ⇄ Open round-trips
