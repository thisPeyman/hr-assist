# 19: Per-user Google connect + draft outreach, human-sent

**What to build:** Email from a real human. From candidate detail, HR clicks Draft email and gets a grounded draft — first-contact outreach or rejection (the interview-invite type arrives with scheduling, ticket 23) — built on Profile + Role + Notes, with tone presets, `[square-bracket placeholders]` for human-only facts, an 80–150 word body, and one CTA. The draft composes in Persian — subject and body, placeholders included — even when the resume is English. HR edits the draft in the draft-email pane and clicks Send; it sends from the HR user's own connected Gmail, so replies land in their normal inbox (no reply-sync in v1). Nothing sends without the human click. Sending requires the user's Google connection (Calendar + Gmail-send in one consent); an unconnected user is prompted to connect before sending. Reuses the OAuth module from ticket 18. Drafts and sends log as Activity. (Spec §8.4, §9, §11 screen 5.)

**Blocked by:** 11 (Upload → parse → Candidate in the Talent Pool) for candidate detail; reuses the Google OAuth module introduced by 18 (either order — whoever lands second reuses).

**Status:** ready-for-agent

- [ ] Per-user Google OAuth connect with Calendar + Gmail-send in one consent; unconnected user prompted before sending
- [ ] Draft generation grounded on Profile + Role + Notes, with tone presets and bracketed placeholders for human-only facts
- [ ] Drafts (subject + body) compose in Persian, even when the resume is English
- [ ] Draft-email pane shows editable subject + body with an explicit "nothing sends without your click" send
- [ ] No code path sends a candidate email without an explicit human click
- [ ] Sends from the connected user's own Gmail; candidate replies land in that inbox
- [ ] Email drafted / email sent logged as Activity
