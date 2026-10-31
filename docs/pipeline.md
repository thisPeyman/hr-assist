# Hiring pipeline

Ticket 12 provides `/board` as the authenticated home, `/roles` and
`/roles/:roleId` for Role creation/ownership/Draft → Open controls, and sourcing
from the board or full-page Candidate detail. The Persian RTL board keeps
Rejected/Withdrawn collapsed at the physical right edge. Dragging and the
keyboard/touch «جابه‌جایی» control open the same explicit confirmation dialog;
context and rejection reason are optional. A move never sends mail.

## API and persistence boundaries

- `GET /api/pipeline/board`, `/stages`, `/owners`: tenant pipeline, current
  Candidate/Role display values, active/inactive attribution. Owner filters,
  including Unassigned, are local board view filters, not protected-attribute
  search. Role owner and Application owner are independent; neither is inferred.
- `POST /api/roles`, `PATCH /api/roles/{id}`: Admin and Member pipeline work.
  Only Draft → Open ships here. Pause/close/bulk ending flows belong to ticket 25.
- `POST /api/roles/{id}/applications`: Open Roles only. The unique database key
  `(candidate_id, role_id)` and shared org transaction lock ensure canonical
  identity under concurrent adds and Candidate Merge. Re-adding live candidacy
  is a no-op; re-adding Hired/Rejected/Withdrawn explicitly reopens the same id
  at Sourced and records Activity, preserving prior owner/history.
- `POST /api/applications/{id}/stage`: human action only. Requires
  `expected_stage_id`; a stale card gets 409 rather than overwriting a newer
  decision. Any destination is explicit, including a return from an ending.
  Optional preset reasons: `experience`, `skills`, `expectations`, `timing`,
  `other`; accepted only for Rejected. Optional `context` holds free text.
- `PATCH /api/applications/{id}/owner`: nullable, same-org active User only.
  Stored inactive attribution remains visible but cannot be newly assigned.
- `GET /api/applications/{id}`: immutable, attributed Application Activity.
  Ticket 17 also returns this Application's own editable Notes; see
  [notes and notifications](notes-and-notifications.md).
  The app role has SELECT/INSERT and only column-level
  UPDATE(application_id), allowing Merge to reparent events without editing
  payload, actor, timestamp or event type. No Activity mutation API exists.

`pipeline_stages` has stable UUID identity and semantic `kind`, independent of
editable names/order. Existing orgs are seeded by migration 0007; future orgs by
signup in the same transaction. Editor/admin mutations belong to ticket 26,
which must preserve identities and extend privileges intentionally.

Migration 0007 **evolves** `candidate_applications`. Every legacy Application
keeps its id, Candidate, timestamp, JSON and original title/stage snapshots.
Each legacy row receives a distinct Draft Role, even if titles match: titles
alone do not establish identity. Known stage kinds map to org Stage ids;
`received` and unknown legacy labels map conservatively to Sourced, with original
values in `legacy_application_imported` Activity. Live display uses joined Role
and Stage records, not legacy snapshots. Tenant composite FKs protect
Candidate/Role/Stage/Application links in addition to scoped queries and FORCE
RLS. Migration changes only the selected database; do not apply it to dev/live
without explicit operator direction.

## Merge and future children

`profiles.merge_applications` runs under the same org identity/workflow lock
before Candidate reassignment. Distinct Roles are unioned. A same-Role collision
retains the **target** Application id/stage/owner without an automatic move,
reparents CandidateNote.application_id and ApplicationActivity.application_id,
then retires the redundant Application. Its source id, stage, owner, creation
time and full JSON survive in `application_merged` Activity. Candidate notes
are subsequently reassigned to the surviving Candidate as usual.

Ticket 17's mentions/notifications reference stable Note ids and resolve links
through the reparented Note; they need no recipient-state mutation during Merge.
Future Application children (Interviews in 23, mail and
other workflow data) **must join this explicit reparent boundary before a
duplicate is deleted**. Do not add a child table and rely on CASCADE to preserve
it. Ticket 26 erasure must include these Activity JSON payloads in its retention/
anonymization inventory; they can contain legacy private data. Ticket 25 should
reuse stage lookup, Application lookup and Activity helpers and preserve the
same explicit/stale-safe mutation contract rather than introduce automatic moves.

## Verification boundary

Public HTTP + isolated PostgreSQL tests cover canonical concurrent adds,
stage changes/reasons, stale decisions, stable kind semantics after rename,
canonical ending reuse, no moves during resume/Role updates, Member work,
tenant/owner rejection, FORCE RLS/restricted grants, database uniqueness/FKs,
immutable events, manual same-Role Merge, automatic email/phone bridge Merge,
distinct-Role union and legacy migration preservation. No live AI/service calls
or dev database writes are needed.

Browser/UI tests are deferred by user decision. Static build/lint and existing
utility tests do **not** prove drag/drop, physical RTL rail layout, focus/mobile
behavior or end-user visual acceptance; those remain manual/browser follow-up.
