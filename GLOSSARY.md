# AI HR Assistant

The hiring context for a SaaS ATS where HR generalists at small companies manage candidates and open roles, with AI embedded in the workflow. This glossary holds the domain language; implementation lives elsewhere.

## Language

### Core entities

**Candidate**:
A person and their profile (contact, skills, work history) in the org-wide Talent Pool, independent of any Role.
_Avoid_: Applicant, contact, lead

**Profile**:
The structured, HR-editable extraction (contact, skills, industries, work history with date ranges) of a Candidate's latest resume; a new resume proposes a diff the HR person accepts or dismisses.
_Avoid_: Parsed data, extraction result

**Role**:
An open job the org is hiring for, with its own owner and lifecycle: Draft → Open → Paused ⇄ Open → Closed.
_Avoid_: Job, position, requisition, opening

**Application**:
A single candidacy joining one Candidate to one Role; holds the stage position, its own notes, and its own activity trail.
_Avoid_: Track, pipeline entry, candidature

**Talent Pool**:
The org-wide set of Candidates, including those not currently applied to any Role.
_Avoid_: Database, resume bank

### Pipeline

**Stage**:
A position in the org's single customizable pipeline (default: Sourced → Screening → Interview → Offer → Hired), held by an Application. Stages are org-wide, not per-Role.
_Avoid_: Status, phase, step

**Merge**:
Attaching an incoming resume to an existing Candidate when identity matches (automatic on email/phone match, human-prompted on fuzzy name match).
_Avoid_: Dedupe, duplicate handling

### Collaboration

**Note**:
Human-written, editable commentary, capable of @Mentions, attached to an Application or a Candidate.
_Avoid_: Comment, message

**Activity**:
An append-only, immutable system event (stage changed, resume added, email drafted, AI summary regenerated) attributed to a user or the system.
_Avoid_: Log entry, audit trail item, history item

**Mention**:
An @-reference to a user inside a Note that raises an in-app notification.
_Avoid_: Ping, tag

**Owner**:
The user assigned accountability for a Role or an Application; optional, and distinct from who performs an action.
_Avoid_: Assignee, recruiter-of-record

### Scheduling & candidate-facing

**Interview**:
A scheduled conversation belonging to one Application: a round label (Phone screen, Video interview, Onsite, Final, or custom), duration, optional location, auto-created Meet link, and a panel of Interviewers.
_Avoid_: Meeting, call, session

**Slot**:
A concrete time an HR user proposes from live Google free/busy, offered to the Candidate for booking.
_Avoid_: Time option, availability window

**Interviewer**:
A person on an Interview's panel, invited by email only — never an app user.
_Avoid_: Panelist, guest user

**Booking Page**:
The single candidate-visible web surface (unguessable tokenized link, no login): pick a Slot, reschedule, or cancel until the org's cutoff.
_Avoid_: Portal, scheduler, candidate dashboard

### Org & tenancy

**Org**:
A customer company; the tenant boundary for all candidate and pipeline data. Created self-serve; its creator becomes the first Admin.
_Avoid_: Workspace, account, tenant

**Admin**:
A User holding org-level powers: inviting and deactivating Users, connecting the System Mailbox, editing the org-wide pipeline, hard-deleting Candidates.
_Avoid_: Owner (reserved for Role/Application accountability)

**Member**:
A User with full pipeline work; everything an Admin can do except the org-level powers.
_Avoid_: User role, staff

**System Mailbox**:
The org-designated Gmail/Workspace address (connected via OAuth by an Admin) that all system email — invites, verification, resets, future digests — sends from.
_Avoid_: No-reply account, notification address
