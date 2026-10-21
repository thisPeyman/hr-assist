# 09 - Assemble the build-ready spec (destination ticket)

Type: task
Status: resolved
Blocked by: 01, 02, 03, 04, 05, 06, 07, 08

## Question

Write the build-ready spec to `.scratch/hr-ai-assistant/spec.md`: v1 scope and non-goals, persona, workflows, domain model (from 05), candidate-facing behavior (06), AI features with their architectures (01, 02, 04), integrations — email-in (03) and Google Calendar — SaaS skeleton (07), screens (08), success criteria, and a short later-phases sketch (event planning, repetitive-task copilot). Review with the human until they would hand it to a build session as-is.

## Context

- This is the destination: when this ticket closes, the map is done.
- Spec format follows the repo tracker convention (`.scratch/hr-ai-assistant/spec.md`).
- Seam from 08: screen vocabulary lives in 08's Answer — Board home (stage columns), full-page candidate detail with editable Profile + AI actions, NL-chips search header, validated ticket-06 flows. Prototype artifact: `prototype/pipeline-ui-prototype.html`.
- The agent can draft alone (AFK) but resolution requires the human's sign-off (HITL review).

## Answer

**Spec written and human-approved as build-ready:** [`spec.md`](../spec.md) — v1 scope/non-goals, persona, workflows, domain model (05), candidate-facing behavior (06), AI features + architectures (01/02/04), integrations (03 email-in + Google Calendar/Gmail), SaaS skeleton (07), screens (08), success criteria, later-phases sketch. Human sign-off confirmed the two spec's-call rulings inherited from 08 (terminal stages = collapsed columns at the board's right edge; no peek-drawer — full-page detail is the only candidate surface) and the new success-criteria and later-phases sections. **The map is done: every decision needed to start building is locked and written down.**
