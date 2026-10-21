# 24: Scheduling lifecycle — reminders, reschedule, cancel, cutoff

**What to build:** The schedule lives on its own. Automated candidate reminders at 24h and 1h before each Interview, composed in Persian and sent from the HR owner's connected Gmail (a scheduled worker extending the Postgres jobs pattern); a morning-of in-app reminder for the HR owner. From the Booking Page the Candidate can reschedule or cancel until the org's cutoff — editable per Org in settings, default 12h, range 2–48h; after the cutoff, changes are refused politely. Cutoff and reschedule messaging render times in Jalali. Cancellation never moves the Application's Stage. Every lifecycle change notifies the HR owner in-app and writes Activity. (Spec §3 Language & locale, §6 W6, §9, §11 screens 7 and 9 cutoff setting.)

**Blocked by:** 23 (Scheduling core — Slots → Booking Page → Calendar).

**Status:** ready-for-agent

- [ ] 24h + 1h candidate reminders send in Persian from the HR owner's Gmail via a scheduled worker
- [ ] Morning-of in-app reminder for the HR owner
- [ ] Reschedule and cancel honored from the Booking Page until the cutoff; refused after — confirmed in tests
- [ ] Cutoff editable per Org in settings (default 12h, validated to 2–48h)
- [ ] Canceling an Interview never moves the Application's Stage; lifecycle changes notify the owner and write Activity
