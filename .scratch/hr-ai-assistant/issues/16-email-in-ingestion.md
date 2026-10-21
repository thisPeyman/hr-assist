# 16: Email-in ingestion

**What to build:** Forward a resume, watch it organize — no GUI touch. An HR user forwards a resume email to the org's address (`resumes+<companySlug>@jobs.<app-domain>`) and the Candidate lands in the pool through the same parse pipeline as uploads. Cloudflare Email Routing on a dedicated subdomain catches all inbound and a thin Worker POSTs the raw MIME (octet-stream) to our webhook with a shared secret; non-matching recipients get a proper SMTP bounce via `setReject()`, not silence; the Worker also parallel-forwards to a backup dead-drop mailbox for durability (Cloudflare won't retry our webhook). The Python webhook durable-writes first — inbox row plus raw .eml in object storage — returns 200, then works async: parse MIME, attachments-first/body-second, strip quoted chains and signatures, ClamAV plus type/size allowlist (pdf/docx/txt/images), then the standard parse pipeline. Idempotency key = Message-ID + recipient, so sender-MTA retries never double-process. The org's email-in address is displayed in settings. No parsing in the Worker. (Spec §7.1.)

**Blocked by:** 11 (Upload → parse → Candidate in the Talent Pool).

**Status:** ready-for-agent

- [ ] Forwarded email with a resume attachment produces a Candidate through the same statuses as upload — nothing dropped silently
- [ ] Webhook durable-writes (inbox row + raw .eml) and returns 200 before any parsing; original retained
- [ ] Persian subjects/bodies (RFC 2047 encoded-words, UTF-8) parse correctly
- [ ] Duplicate delivery (same Message-ID + recipient) is processed exactly once
- [ ] Virus or disallowed-type attachments end in a safe explicit status, never a crash
- [ ] Non-matching recipient → real SMTP bounce, not silence
- [ ] Org email-in address visible in settings
