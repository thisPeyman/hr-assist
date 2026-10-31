# Notes, mentions and in-app notifications

Ticket 17 evolves `CandidateNote` / `candidate_notes`; there is no second note
store. The full-page Candidate's «یادداشت‌ها و درخواست‌ها» tab shows all notes,
Candidate-only notes, or one Application's own notes. Board cards and the
Candidate's Application list link to the Application-specific view. The editor
chooses scope when creating a note, not when editing one. Existing MUI/Emotion,
Vazirmatn, blue/slate outlined surfaces, Persian labels and RTL remain in place.
The scope-colored note edge distinguishes Application commentary from the
Candidate record; there is no second timeline pretending editable text is audit.

## Public API

- `POST /api/candidates/{id}/notes` — Candidate note.
- `POST /api/applications/{id}/notes` — Application note; Candidate is resolved
  from that Application on the server, never accepted from an untrusted payload.
- `PUT /api/notes/{id}` — replace `body` (trimmed, nonempty, at most 10,000
  characters) and `mention_user_ids` (explicit UUID list, at most 100).
- `GET /api/candidates/{id}/workspace` — aggregate all Candidate/Application
  notes. `GET /api/applications/{id}` — only that Application's notes and its
  immutable Activity. Note DTOs include fixed author, last editor, creation/edit
  dates, scope, explicit mention ids, and active/inactive person attribution.
- `GET /api/notes/mention-users` — only same-org active selectable users. Plain
  `@text` is not interpreted as identity; the accessible multiple-choice picker
  inserts readable @email text and submits stable UUIDs separately. Changing text
  alone does not change the explicitly selected recipients.
- `GET /api/notifications` — personal newest 100 notifications and total unread
  count (including older rows). `PATCH /api/notifications/{id}` with `read: bool`
  marks only the current recipient's row read/unread. Missing/foreign rows 404.
  Opening the list alone does not mark anything read. Opening a note explicitly
  marks its notification read; a separate control can reverse that state.

## Permission and delivery rules

Admin and Member have full same-org collaboration rights (spec §5/§10): any
active member can create/edit a note. There is no undocumented author-only or
Admin-only gate. Author and scope cannot be changed through the API; only the
last editor and edit timestamp change. Unknown input fields (including forged
author/Application/Candidate ids) are rejected. Existing inactive mentions may
remain on an edited note for attribution, but cannot be newly selected or added;
inactive users cannot use the API. Deactivation preserves author/editor/mention
identity and displays it as inactive. User administration itself belongs to 18.

New recipients get one notification per `(org, recipient, note_mention:<note>)`.
Repeated, concurrent or unchanged edits do not duplicate delivery or reset read
state. Adding another recipient delivers to that recipient only. Removing a
mention removes the current mention relationship but retains the historical
notification and its read state; re-adding it does not notify twice. Self-mentions
are explicit and supported. No mention path imports/calls mail or Google; these
are in-app-only notifications, not deferred email jobs.

`notifications.notify` is a transaction-local idempotent helper for trusted
future workflow callers, validating same-org active recipient and accepting kind,
dedupe key and optional Note reference. It does not commit or send email. Tickets
23/24 should extend their structured target reference and resolver deliberately
alongside their own domain models, not accept arbitrary client URLs or create a
second delivery system. No scheduling or Google feature ships in ticket 17.

## Persistence and Merge

Migration **0009** extends existing Notes, adds `note_mentions` and
`notifications`, forced RLS and explicit grants. Note author/editor, mention user,
notification recipient and Note targets have composite tenant FKs. The
Application note FK also includes Candidate identity; it is initially deferred
so ticket 12's existing `profiles.merge_applications` can reparent Application
then Candidate within one atomic Merge. Cross-Candidate Application attribution
is rejected at transaction completion. Original note author/time/id survive.
Distinct-Role applications retain their own notes; same-Role coalescing reparents
notes before retiring the duplicate. Mention/notification rows refer to the stable
Note, so they survive both manual and email/phone bridge auto-Merge unchanged.

Every HTTP tenant context pins both transaction-local `app.current_org_id` and
`app.current_user_id`. Notification SELECT/UPDATE RLS requires **both** matching
org and recipient; INSERT can target a validated same-org recipient for delivery.
The app role gets notification SELECT/INSERT and only UPDATE(read_at), no DELETE
or table-wide UPDATE. Note updates use narrow columns; author/time cannot be
edited as `hr_app`. Activity retains its existing immutable payload/actor/time
privileges, with only the established Merge reparent columns writable. Note
create/edit append scoped `note_added`/`note_edited` events with note id only,
never mutable body snapshots.

Notification links are server-generated from the **current Note reference**,
not stored Candidate/Application URLs. They remain safe after Merge and cannot
be external redirects. The frontend accepts only the narrow internal UUID-based
Candidate-note link shape. The bell refreshes on open, focus, local note changes
and once per minute, with explicit error/retry and unknown-count states.

Ticket 26 erasure must include Notes, current mentions and their cascaded
notifications, and anonymize retained Activity as specified. This ticket does
not add candidate deletion or membership removal APIs. Run migrations only on
an explicitly selected operator-approved database; verification uses disposable
Docker `hr_test`, never the development database.

## Verification boundary

`tests/test_notes_notifications.py` exercises public HTTP plus real isolated
Postgres for edit attribution, Member access, inactive selection/retention,
cross-tenant refusal, new/removed/re-added mentions, recipient privacy/read state,
unchanged concurrent edits, aggregate/Application-only views, manual Merge,
current deep links and no external mail/HTTP calls. Raw SQL tests run as
`hr_app` and prove FORCE RLS, unset-GUC denial, recipient scoping, restricted
grants, rejected foreign-tenant FKs and mismatched Candidate/Application links.
The existing email/phone bridge Merge API regression now includes a mentioned
Application note and verifies its canonical link afterward.

Final checks: full backend **278 passed**; Ruff clean; frontend TypeScript/Vite
build passed, **25 existing utility tests passed**, oxlint zero errors/four
pre-existing warnings. Build retains its existing >500KB chunk advisory.
No new browser/UI tests, visual/keyboard/mobile acceptance, paid/live providers,
real email or dev DB migrations were run. Browser acceptance is explicitly
deferred by the user; static checks do not prove those interactions.
