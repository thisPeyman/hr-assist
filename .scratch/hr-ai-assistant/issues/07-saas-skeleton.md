# 07 - SaaS skeleton: tenancy, auth, roles, billing

Type: grilling
Status: resolved

## Question

What does the SaaS skeleton of v1 look like? Settle: the org/user model and multi-tenancy approach; auth on a build-not-buy stack (rolled with an OSS library vs. a hosted IdP — is a hosted IdP "buyable"? put it to the human); roles/permissions (org admin vs. member, and whether hiring-manager guests exist in v1); and whether v1 ships with billing at all (pilot-free first?) or wires payments from day one.

## Context

- Call the `grilling` and `domain-modeling` skills. Use the standard question box for every question.
- Build-not-buy constraint (map Notes): OpenAI API is the only paid external dependency — where does the human draw the line for auth/payments infra?
- Informed by competitive pricing research (01) but not blocked by it. May graduate the pricing fog on the map.
- Seam from 01: the market wedge is **flat pricing with unmetered AI** (incumbents meter AI via credit add-ons; flat band starts at $157/mo, per-seat floor $15/user) and a **compliance-forward "no scoring — human decides"** stance — the billing/tenancy decisions here should fit that shape, not fight it.
- Seam from 05: org-admin powers already include hard-deleting Candidates and editing the org-wide pipeline — fold these into the roles/permissions split.
- Seam from 06: user records carry per-user Google OAuth tokens (Calendar + Gmail send) — a user-level secret next to the org-level tenancy model.

## Answer

Tenancy terms live in `GLOSSARY.md` (Org, Admin, Member, System Mailbox).

**Tenancy.** Org + User + Membership, **one Org per User in v1** (multi-org membership is a later-phase seam, not designed in). Self-serve Org creation: anyone signs up and their Org's first **Admin**. Isolation: one shared Postgres schema, `org_id` on every tenant-owned row, app-layer scoping **plus Postgres Row-Level Security** enforcing the same rule as a belt-and-braces net.

**Auth.** **Self-rolled on a mature Python OSS library** (e.g. fastapi-users): email + password with verification, argon2, cookie sessions, **optional TOTP 2FA** any user can enable. No hosted IdP — the OpenAI-only paid-dependency line holds. Admin actions (invites, mailbox connected, pipeline edited) extend the Activity pattern from 05 into an org-level stream.

**System email.** At setup an Admin connects the **System Mailbox** — an org-designated Gmail/Workspace address via the same OAuth flow HR users use. All system email (invites, verification, resets, future digests) sends from it. One email integration, one deliverability story, no personal-account ownership of system identity.

**Roles.** **Admin + Member**, nothing finer in v1. Admin powers: invite/deactivate Users, connect the System Mailbox, edit the org-wide pipeline, hard-delete Candidates (from 05). Members do all pipeline work. **Only Admins invite; removal is always DEACTIVATE, never delete** — Notes and Activity keep attribution, Google tokens revoked, name greyed out. No guest role (settled in 05/06).

**Billing.** **Deferred entirely (human's explicit call over the recommendation): v1 ships pilot-free with no billing wired AND no plan/pricing model designed in.** The 01 wedge (flat per-org, unmetered AI) remains positioning guidance, not schema. Pricing fog stays open on the map until pilot conversations validate it.

**Deferred to fog.** Org self-serve data export (JSON/CSV) — not in v1, handled manually on request.
