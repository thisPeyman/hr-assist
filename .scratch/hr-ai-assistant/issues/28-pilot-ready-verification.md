# 28: Pilot-ready verification — success criteria pass

**What to build:** Prove the spec's seven success criteria on a fresh Org, end to end, fixing what fails. (1) Time-to-value: signup → email-in connected → a parsed, AI-summarized Candidate in the pool within 15 minutes, no sales touch. (2) Nothing dropped: every submitted document ends in an explicit terminal status; `needs_review` is visible and workable in the UI. (3) Costs and latency at envelope: parsing ≤ $5/1k at typical mix; search p50 ≈ 1s and <$0.001/search. (4) Compliance posture holds end-to-end: zero scoring/ranking/fit verdicts anywhere in product or prompts; protected-attribute filters blocked at the validation layer; every candidate-facing email required an explicit human send; AI outputs say "not stated" rather than inventing. (5) Scheduling round-trip: propose → book on the Booking Page → Calendar event with Meet link → 24h/1h reminders → reschedule/cancel honored until cutoff — and no stage ever moves automatically. (6) Tenancy airtight: RLS enforced, app-layer scoping, deactivate-only removal with attribution preserved. (7) Pilot loop: an HR generalist runs ingest → pipeline → search → compare → outreach → schedule → hire/reject entirely in-app. (Spec §13.)

**Blocked by:** all of 10–27.

**Status:** ready-for-agent

- [ ] Fresh-Org run reaches a parsed, summarized Candidate within 15 minutes including email-in connection
- [ ] Nothing-dropped audit passes: every test document ends in an explicit terminal status; queue is workable
- [ ] Measured costs/latency sit inside the envelope (parse, search p50 and cost)
- [ ] Compliance sweep passes: no scoring/ranking/fit verdicts; blocklist enforced; human-send required everywhere; "not stated" behavior holds
- [ ] Scheduling round-trip verified incl. reminders and cutoff; zero automatic stage moves
- [ ] Tenancy tests pass: RLS + app-layer scoping; deactivate-only removal
- [ ] Full W1–W7 loop completes in-app without leaving for spreadsheets or a separate scheduler
- [ ] Persian-first UX verified end-to-end: RTL everywhere, Jalali dates, Persian AI outputs and emails, mixed fa/en resumes handled
