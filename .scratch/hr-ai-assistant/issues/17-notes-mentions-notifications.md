# 17: Notes, @Mentions, in-app notifications

**What to build:** Collaboration on the record. HR writes editable Notes with @Mentions attached to an Application or a Candidate; both levels get aggregated views (a Candidate's notes across all their Applications, an Application's own notes). An @Mention raises an in-app notification for the mentioned user — a bell with unread state and a notification list. In-app only: v1 sends no email notifications. (Spec §5 Notes & Activity/Collaboration, §11 screen 3.)

**Blocked by:** 12 (Board home — Roles, Applications, Stages).

**Status:** ready-for-agent

- [ ] Notes creatable and editable at Application and Candidate levels, with aggregated views at both levels
- [ ] @Mention inside a Note raises an in-app notification for the mentioned user
- [ ] Bell + notification list surfaces unread state
- [ ] No email notifications sent for mentions (in-app only in v1)
