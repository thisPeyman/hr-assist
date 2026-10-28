# 16: Email-in ingestion

**What to build:** Forward a resume, watch it organize — no GUI touch. An HR user forwards a resume email to the org's address (`resumes+<companySlug>@jobs.<app-domain>`) and the Candidate lands in the pool through the same parse pipeline as uploads. Cloudflare Email Routing on a dedicated subdomain catches all inbound and a thin Worker POSTs the raw MIME (octet-stream) to our webhook with a shared secret; non-matching recipients get a proper SMTP bounce via `setReject()`, not silence; the Worker also parallel-forwards to a backup dead-drop mailbox for durability (Cloudflare won't retry our webhook). The Python webhook durable-writes first — inbox row plus raw .eml in object storage — returns 200, then works async: parse MIME, attachments-first/body-second, strip quoted chains and signatures, ClamAV plus type/size allowlist (pdf/docx/txt/images), then the standard parse pipeline. Idempotency key = Message-ID + recipient, so sender-MTA retries never double-process. The org's email-in address is displayed in settings. No parsing in the Worker. (Spec §7.1.)

**Blocked by:** 11 (Upload → parse → Candidate in the Talent Pool).

**Status:** resolved

- [x] Forwarded email with a resume attachment produces a Candidate through the same statuses as upload — nothing dropped silently
- [x] Webhook durable-writes (inbox row + raw .eml) and returns 200 before any parsing; original retained
- [x] Persian subjects/bodies (RFC 2047 encoded-words, UTF-8) parse correctly
- [x] Duplicate delivery (same Message-ID + recipient) is processed exactly once
- [x] Virus or disallowed-type attachments end in a safe explicit status, never a crash
- [x] Non-matching recipient → real SMTP bounce, not silence
- [x] Org email-in address visible in settings


## Answer

Implemented authenticated raw-MIME ingestion, bounded streaming, envelope-recipient Org lookup, durable local/S3 blob storage before HTTP acknowledgement, unique delivery keys, async Postgres receipt processing, MIME attachments/body fallback, Persian headers/filenames, ClamAV fail-closed quarantine and rescan. Added the thin Cloudflare Worker with backup forwarding and SMTP rejection, placeholder configuration, and a local synthetic-MIME/replay CLI. Per the user's instruction, no real domain, DNS or cloud deployment was configured. Settings show the per-Org address when enabled. See [runtime and mock-test instructions](../../../docs/resume-ingestion.md).

Validation: backend API/worker/storage/quarantine/isolation tests, 4 Node Worker tests and browser verification of Persian MIME plus duplicate delivery. Scanner/model/remote storage transports are mocked in automated integration tests; no live email was sent.
