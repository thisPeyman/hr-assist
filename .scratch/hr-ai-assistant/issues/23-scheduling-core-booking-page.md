# 23: Scheduling core — Slots → Booking Page → Calendar

**What to build:** The scheduling round-trip, end to end. From an Application, HR proposes 2–4 concrete Slots checked against connected HR users' live Google free/busy, names an email-only Interviewer panel (name + email, never app users), and drafts the interview-invite email — grounded, human-sent from the proposer's Gmail — wrapping the link to the Booking Page. The Booking Page is the single candidate-visible surface: unguessable tokenized link, no login, in Persian with RTL layout and Jalali date/time display, rendered in the candidate's browser timezone, offering pick / reschedule / cancel. When the Candidate books, the event appears on the slot-proposer's calendar with the Candidate + panel as attendees and an auto-created Meet link; sibling Slots are released; the HR owner is notified in-app and every candidate action writes Activity. Cancel never moves the Stage. (Spec §6 W6, §9, §11 screens 6–7.)

**Blocked by:** 12 (board — Application context), 17 (in-app notifications to the HR owner), 19 (per-user Google connect + human-sent email).

**Status:** ready-for-agent

- [ ] Propose 2–4 Slots from an Application, checked against connected users' live free/busy; unconnected proposer prompted to connect
- [ ] Interviewer panel is email-only — name + email, never an app user
- [ ] Interview-invite draft email wraps the Booking Page link; human-sent from the proposer's Gmail
- [ ] Booking Page: unguessable tokenized link, no login, candidate's timezone — Persian, RTL, Jalali times
- [ ] Booking creates the calendar event on the proposer's calendar with candidate + panel attendees and an auto-created Meet link; sibling Slots released
- [ ] Candidate actions notify the HR owner in-app and write Activity; no Stage moves automatically
