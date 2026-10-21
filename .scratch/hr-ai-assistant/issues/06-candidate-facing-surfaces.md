# 06 - Candidate-facing surfaces: scheduling, outreach, portals

Type: grilling
Status: resolved

## Question

What does the candidate-facing side of v1 look like? Settle: end-to-end interview scheduling behavior (availability windows, booking-link emails, round-robin among interviewers, Google Calendar event creation, reminders, reschedule/cancel); whether AI-drafted outreach is draft-only or sent from the app — and how, given build-not-buy; and whether v1 has any candidate-visible pages at all (booking page, application portal, status page) vs. email-only.

## Context

- Call the `grilling` and `domain-modeling` skills. Use the standard question box for every question.
- Google Calendar only in v1; the design should leave a clean seam for Outlook later (map fog).
- Seam from 05: core entities live in `GLOSSARY.md` (Candidate/Role/Application pool-first, org-wide stages, Notes+Activity, reopenable applications) — extend the glossary with scheduling/candidate-facing terms (e.g. Interview, booking) rather than redefining core ones. In-app-only notifications in v1 mean an outbound-email path here is optional, not assumed.
- The GUI prototype (08) blocks on this.

## Answer

All decisions below; scheduling terms live in `GLOSSARY.md` (Interview, Slot, Interviewer, Booking Page).

**Outreach email.** v1 **sends from the app via the HR user's own connected Gmail/Workspace account** (Gmail API send scope, granted together with Calendar in one OAuth flow). Deliverability rides on Google; the sender is a real human the candidate replies to; replies land in the HR user's normal inbox — **no reply-sync in v1**. AI drafts three email types — first-contact outreach, interview invite (wrapping the booking link), and rejection — grounded on Profile + Role + Notes, with placeholders and tone presets. **Every email is shown for human edit and explicit send — nothing leaves without a human clicking send** (consistent with the compliance-forward stance from ticket 01).

**Scheduling flow.** HR proposes **2–4 concrete Slots** in-app, checked against live Google free/busy of all connected users (no Calendly-style availability-rules engine in v1). The candidate receives an email linking to the **Booking Page** — the only candidate-visible surface (public, unguessable tokenized link, no login; no application portal, no status page in v1) — picks a slot, and the system confirms: Google Calendar event created on the slot-proposer's calendar with candidate + panel as attendees, **auto-created Meet link**, slot siblings released. Unbooked slots self-expire when past. The Booking Page renders times in the candidate's browser timezone.

**Panels.** An Interview belongs to one Application and holds a panel of **Interviewers — name + email only, never app users** (no seat, no login; consistent with no-guest-access in 05). Free/busy is checked only for connected HR users; external Interviewers get plain invites and accept/decline in Google (not synced into the app in v1). No round-robin pools.

**Reminders & changes.** Automated candidate reminders at **24h and 1h before**, sent from the HR owner's Gmail; in-app morning-of reminder for the HR owner. Candidate can reschedule/cancel via their link **until a per-org configurable cutoff (default 12h, range 2–48h)** — freed slots release automatically. Every candidate action fires an in-app notification to the HR owner + an Activity entry. HR can cancel/reschedule freely. **Cancel never touches the pipeline stage** — a completed or cancelled interview is only an Activity entry; stage moves are always human.

**Google mechanics.** **Per-user OAuth** (Calendar + Gmail send in one consent). Events live on the slot-proposer's calendar; an HR user without a connected account is prompted to connect and can't propose slots meanwhile. The integration boundary (who proposes/hosts/sends) is the seam a future Outlook integration implements.

**Handed forward.** 08: prototype should cover the Booking Page, the slot-proposing flow, and the draft-with-approval email pane. 07: user records carry per-user Google OAuth tokens. 09: all of the above is spec-ready; the careers-page/portal question is settled as **not in v1**.
