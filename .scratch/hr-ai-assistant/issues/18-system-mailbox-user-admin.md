# 18: System Mailbox + user administration

**What to build:** The org's voice. An Admin connects the System Mailbox — an org-designated Gmail/Workspace address via OAuth — and all system email sends from it, composed in Persian: Member invites, email verification, password resets (the verification deferred from ticket 10 lands here). Only Admins invite; removal is always deactivate — attribution preserved, Google tokens revoked, name greyed out; there is no hard user delete. Admin actions (invite sent, user deactivated, mailbox connected) append to the org-level Activity stream. The Users screen lists Members with invite and deactivate actions. This ticket builds the shared Google OAuth module that ticket 19's per-user connect reuses — same flow, different grantee (Org vs User). (Spec §5, §9 System Mailbox, §10, §11 screen 9.)

**Blocked by:** 10 (Org & auth walking skeleton).

**Status:** ready-for-agent

- [ ] Admin connects the System Mailbox via OAuth; connection status visible in settings
- [ ] Invite by email arrives from the System Mailbox, composed in Persian; recipient joins as a Member
- [ ] Email verification and password-reset emails deliver from the System Mailbox
- [ ] Deactivate-only user removal: attribution preserved, tokens revoked, greyed name; no hard delete path exists
- [ ] Admin-only powers enforced for invite and mailbox connect; a Member attempting them is refused (tested)
- [ ] Admin actions append to the org-level Activity stream
- [ ] Google OAuth connection module is reusable for per-user connect (ticket 19)
