# Research 03 — Receiving inbound email on a build-not-buy stack

- **Ticket**: [03-inbound-email-options](../issues/03-inbound-email-options.md)
- **Date researched**: 2026-10-21 (web-verified against current docs/pricing)
- **Question**: How do we receive mail at an `@app-domain` address (users forwarding candidate resumes) and trigger a Python webhook with attachments — self-hosted SMTP on a VPS, Cloudflare Email Routing → Worker, or something else? Pick v1 + upgrade path.
- **Constraint line (from map)**: OpenAI API is the only paid external dependency; free infra tiers are acceptable.

---

## TL;DR

**v1: Cloudflare Email Routing → thin Email Worker → HTTP POST of raw MIME to our Python webhook.** Free, unlimited inbound volume, no servers, and the mail never depends on our app's uptime because senders' MTAs retry during outages. Keep the Worker a *thin relay* (stream bytes, don't parse) to stay inside the free plan's 10 ms CPU limit, and parse MIME/attachments in the Python app. Add a **parallel catch-all forward to a backup mailbox** for durability (a well-documented "multipath" pattern) since Cloudflare won't retry our webhook for us.

**Not for v1:** self-hosted Postfix/maddy on a VPS (no free VPS can receive mail — Oracle free tier blocks port 25; paid VPS breaks the $0 line — and it's the highest-ops option), and ImprovMX (webhooks are $9/mo, Premium-only). **Upgrade path:** stay on Cloudflare and add Queues/R2 + $5/mo Workers Paid when volume or durability demands bite; graduate to Amazon SES receiving (~$0.10/1k) only if we outgrow Cloudflare's free tier or need an SLA'd pipeline.

---

## How we judged

For a *receive-only* address, the classic self-hosting fear (IP reputation, rDNS, DNSBLs) mostly doesn't apply — those govern **sending**. What actually matters here:

1. **Cost line** — $0, or free tier with real headroom.
2. **Reliability** — does mail survive (a) our app being down, (b) the provider being down, (c) a handler bug?
3. **Deliverability (inbound sense)** — do HR users' forwards from Gmail/Outlook actually reach the MX and get accepted? Are rejects/bounces visible to the sender?
4. **Spam & attachments** — what junk reaches the webhook; can 1–25 MB PDF/DOCX attachments arrive intact and be parsed in Python?
5. **Ops burden** — patching, monitoring, config surface we own.

Expected volume for v1: HR users at small companies forwarding resumes — **dozens of emails/day, tens of companies** — i.e. tiny. Attachments: resumes are typically < 5 MB; Gmail/Outlook can't even attach > 25 MB to a forwarded message (Gmail converts oversized to Drive links).

---

## Option A — Cloudflare Email Routing → Email Worker → webhook ✅ (recommended)

### 2026 state of the product

Cloudflare folded Email Routing into a new **"Cloudflare Email Service"** (public beta of Email Sending announced April 16, 2026). For us the important half is unchanged: **Email Routing is free, and inbound is unlimited** on the Workers Free plan. (The new Email *Sending* half is Workers-Paid-only — irrelevant to v1 ingestion, but a candidate for the later outreach-email feature.)

### Verified limits that matter (docs, Sep–Oct 2026)

| Limit | Value | Impact on us |
|---|---|---|
| Inbound emails | **Unlimited, free** | No cap at any volume we'll hit |
| Inbound message size | **25 MiB** (larger rejected) | Matches Gmail's own 25 MB send cap — non-issue |
| Routing rules per domain | 200 | We use **one catch-all rule → Worker**; irrelevant |
| Workers Free plan | 100k req/day, **10 ms CPU/invocation** | The real constraint — see "thin relay" below |
| Email Workers on free | Supported; docs explicitly warn complex handlers may hit `EXCEEDED_CPU` and fail | Shapes the architecture |
| Queues on free | Since Feb 2026: 10k ops/day, **24 h retention** | Enough as a retry buffer for our volumes |

### The architecture

```
HR user's mail client
  └─ forwards resume → resumes+acme@jobs.ourapp.com
       └─ MX: Cloudflare Email Routing (anycast, free)
            └─ catch-all rule → Email Worker (email() handler)
                 ├─ fetch() POST message.raw (octet-stream) → our Python webhook
                 │     └─ Python: email lib parses MIME, extracts attachments,
                 │        tenant from recipient local-part, ClamAV/libmagic scan,
                 │        size/type allowlist → ingest pipeline
                 └─ message.forward(backup@ourapp.com)  // durable dead-drop copy
```

Worker code is ~20 lines (TS or Python — Cloudflare's email handler docs now show a Python variant, pleasing for a Python shop): read `message.raw` (a `ReadableStream`), POST it to the webhook with a shared-secret header, and forward a copy to the backup mailbox. `message.rawSize`, `message.headers`, `message.from/to` are available for cheap pre-checks.

**Why "thin relay" (don't parse MIME in the Worker):** free plan CPU is 10 ms/invocation and Cloudflare's own limits page warns heavy handlers fail with `EXCEEDED_CPU`. Streaming bytes to our server and parsing with Python's stdlib `email` module costs ~0 CPU in the Worker and keeps all parsing logic in the app where it's testable and debuggable. (The docs' suggested `postal-mime` parsing is exactly the work we push to Python.)

**Tenant routing without extra rules:** one catch-all address like `resumes+<companySlug>@…` (or `resumes@<slug>.ourapp.com` sub-domains if we want per-company addresses); the Worker passes the envelope recipient through and Python resolves the tenant. The `+tag` also acts as a weak gate against strangers emailing the address — a company's slug is effectively a shared secret.

### Reliability, honestly assessed

- **Provider outages are real but survivable.** Cloudflare had a ~6-hour global outage (Nov 18, 2025) that hit Email Routing, plus shorter ones (Dec 5, 2025 ~25 min; Mar 2025 ~1 h). During inbound outages, **senders' MTAs keep retrying for ~24–48 h**, so brief outages self-heal — forwarded resumes arrive late, not lost. 
- **No application-level retry of your webhook.** If the Worker runs but our app returns 5xx, Cloudflare does not re-POST; a failed handler invocation may bounce or drop. Mitigations (cheap, all free): (1) the Worker forwards every message to a **backup mailbox** (free Gmail/Outlook via verified destination address) — the documented "multipath routing" pattern from the Cloudflare community — so nothing is ever unrecoverable; (2) our webhook enqueues to our own DB/queue and returns 200 only after durable write; (3) if we want an explicit buffer, Worker → **Queues** (free tier) → consumer → webhook, with the 24 h retention caveat.
- **The known Gmail-reputation incident (Mar 2024) doesn't touch this design.** Gmail temporarily rate-limited *Cloudflare forwarding IPs* (451 4.7.650) — that hurt Worker→Gmail forwarding chains, not Worker→HTTP. One more reason the primary path is the direct HTTP POST, with the Gmail forward as the passive backup only. (Gmail has also been seen spam-foldering Cloudflare-forwarded mail; the backup mailbox is for durability, not primary delivery.)

### Spam handling

There is **no managed spam filter in the Email Routing path** — the Worker sees everything. Cloudflare's own docs offer a heuristic spam-filter *example* (subject keywords, sender-domain scoring, optional Workers AI). For our narrow case that's enough: expected senders are *authenticated HR users forwarding from their corporate mail*. Practical gates, all in the Worker (cheap) or Python (thorough):

- recipient must match a known `resumes+slug` pattern, else `setReject()` (SMTP-level reject — the sender sees a bounce, not silence);
- per-company slug must exist / optional per-company token in the address;
- Python-side: attachment allowlist (pdf/docx/txt/images), size caps, ClamAV (clamd socket or containerized) — **resumes are untrusted binaries regardless of transport choice**, so this work isn't avoidable in any option.

### Deliverability (inbound sense)

Point MX at Cloudflare's anycast MX hosts (auto-configured, with SPF/DKIM/DMARC records added automatically). Gmail/Outlook deliver to Cloudflare's MX without complaint — this is the same infrastructure carrying huge volumes of personal-domain forwarding. Rejects we issue via `setReject()` produce proper SMTP bounces to the forwarder.

### Ops burden

Near zero: no servers, no certs, no queue babysitting. We own ~50 lines of Worker code (deployable/configurable via Wrangler including routing rules as code, testable locally with `wrangler dev` email simulation), plus monitoring: Workers logs + Email Routing activity log (per-message Forwarded/Dropped/Delivery-failed status) and an alert on our webhook's 5xx rate. The one operational discipline required: keep the dead-drop backup mailbox verified and monitored.

### Score

Reliability: **B+** (outages self-heal via sender retries + dead-drop; no app-level retry is the gap we patch ourselves). Deliverability: **A−**. Spam/attachments: **B** (DIY, but easy for a closed sender population). Ops: **A**. Cost: **$0**.

---

## Option B — Self-hosted SMTP receiver on a VPS (Postfix / maddy / Stalwart)

### What it looks like

Postfix configured receive-only (no submission relay): MX → `postscreen` + TLS (Let's Encrypt) → optional `rspamd` milter for spam → local delivery piped to a small Python script (alias `"|/app/bin/mail-webhook"`) that POSTs the raw message to the app webhook — or Maildir delivery + a poller. **maddy** (single Go binary, actively maintained) and **Stalwart** (all-in-one Rust server, the 2024–2026 darling) are simpler to stand up but are designed around their own storage/IMAP; piping inbound to an HTTP webhook is not a first-class pattern in either — you'd deliver to storage and poll. For receive→webhook, **Postfix is still the right tool**: `pipe(8)` to a script is exactly its job.

### The port-25 reality check (verified)

- **Inbound port 25 is open** on mainstream VPS providers (Hetzner, DigitalOcean) — users consistently confirm "I can receive but not send"; what's blocked is *outbound* 25 (DO blocks 25/465/587 outbound by default; Hetzner blocks outbound 25, unblocks on request).
- **The free-VPS escape hatch is closed**: Oracle Cloud (the only meaningful always-free VPS) blocks port 25 by default for tenancies since June 2021, and support routinely refuses to reopen it even for paid accounts — inbound included.
- So Option B requires a **paid VPS (~$4–6/mo)**, which crosses the constraint line the way a paid email API would. It fails "free" harder than it fails anything technical.

### The actual trade

Receiving is the *easy* half of self-hosted email — no sender reputation needed, senders don't check the receiver's IP, retries cover brief downtime. What you buy with it: total control, zero third-party data path, no platform outage coupling. What you pay with, forever:

- an internet-exposed MTA to patch (Postfix CVEs are rare but real; rspamd/clamav more frequent);
- a public catch-all address on a fresh domain **will** be hammered by spam/backscatter scans — you own the filtering and the log noise;
- silent-failure modes (a bad `main.cf` edit after an upgrade = mail bounces with nobody watching);
- storage, queue monitoring, certbot renewals, fail2ban.

For a *core product ingestion path* at ~$0 savings versus Cloudflare, this is the wrong trade in v1. It becomes interesting only if we later want capabilities Cloudflare can't offer (Sieve rules, SRS control, on-prem data-path requirements) — and by then we can afford the $5/mo.

### Score

Reliability: **B** (sender retries + our own queue, but single box, no redundancy). Deliverability: **A** (we ARE the MX). Spam/attachments: **B+** (rspamd + ClamAV are mature and strong). Ops: **D**. Cost: **$4–6/mo** (fails constraint).

---

## Option C — Free-tier / borderline managed services (the 2026 field)

| Service | Inbound webhook? | Free tier? | Verdict |
|---|---|---|---|
| **ImprovMX** | Yes — good one: JSON + base64 attachments, `raw_mime`, spam check, **2 retries** on 4xx/5xx, static source IP | **No** — webhooks are Premium ($9/mo). Free = forward-to-mailbox only, 500/day, 99% uptime "guarantee" | Best-documented cheap fallback, but fails the $0 line |
| **Forward Email** (forwardemail.net) | Yes (API/webhooks) | Free = forwarding only; webhooks/API are paid (~$3/mo tier) | Open-source codebase is nice; free tier doesn't do webhooks |
| **Mailtrap** | Yes — hosted `@inbound.mailtrap.io` addresses (no MX needed), custom domain connectable | **4,000 inbound/mo free** | Credible free-tier managed option; newer inbound product; per-inbox caps until domain connected. Keep as Cloudflare alternative |
| **Pingram** (ex-NotificationAPI) | Yes — inbound email→webhook, attachments in payload | **3,000/mo free**, $0.50/1k after | Fits the letter of the constraint; young vendor, rebrand in progress — concentration risk on a core path |
| **Resend** | Yes (inbound routes) | 3k/mo but **100/day cap**; product identity is outbound | Cap too tight, path too new for a core ingestion channel |
| **SendGrid Inbound Parse / Mailgun Routes / Postmark** | Yes, mature | **No** — $15–20/mo entry | The "buy" options the constraint defers |
| **Amazon SES receiving** | Via S3 + Lambda/SNS | No free inbound; **$0.10 per 1k** (chunked 256 KB) | Pennies at our volume but requires AWS plumbing + paid account; the natural *graduation* target |

**Gmail/IMAP-poll variant (worth naming, not choosing):** Cloudflare Email Routing → forward to a free Gmail → Python IMAP-IDLE poller picks up messages/attachments. World-class spam filtering at $0, but adds a second hop (inheriting the Cloudflare→Gmail reputation flakiness documented in 2024), polling latency, app-password fragility, and Google ToS gray areas for automation. Strictly worse as a primary than the Worker→webhook POST; its correct role is the **backup dead-drop** in Option A.

---

## Comparison summary

| Criterion | A: CF Routing→Worker | B: VPS + Postfix | C: free managed (Mailtrap/Pingram) |
|---|---|---|---|
| Cost | **$0** | $4–6/mo | $0 (capped) |
| Setup | ~half a day | 1–2 days + hardening | ~half a day |
| Reliability | B+ (retry-by-sender + dead-drop) | B (single box) | B/B+ (vendor-dependent) |
| Deliverability (inbound) | A− | A | A− |
| Spam handling | DIY-but-easy | Strong (rspamd) | Varies (ImprovMX good, but paid) |
| Attachments→Python | Raw MIME, we parse | Raw MIME, we parse | Pre-parsed JSON (less control) |
| Ops burden | Minimal | Highest | Minimal |
| Lock-in exit cost | Low (change MX, redeploy) | None | Low-moderate |
| Volume ceiling (free) | **Unlimited** | n/a (paid) | 3–4k/mo |

---

## Recommendation

**v1 = Option A.** Rationale in one breath: it is the only option that is genuinely $0 at *unlimited* inbound volume, has no servers to operate, keeps attachments as raw MIME under our full control, and whose two real weaknesses (no webhook retry, DIY spam) are both cheaply patched with patterns the community already runs in production (multipath dead-drop forward; slug-gated recipient + `setReject`).

**Concrete v1 commitments** (feed into spec 09 ingestion design):

1. Address shape: `resumes+<companySlug>@jobs.<app-domain>` (dedicated sub-domain keeps the zone's other mail concerns isolated). One catch-all routing rule → one Worker.
2. Worker contract: stream `message.raw` → `POST` to `https://api.<app-domain>/hooks/inbound-mail` with `X-Webhook-Secret`; parallel `message.forward(backup@…)` dead-drop; `setReject` only for non-matching recipients.
3. Python webhook: durable-write first (inbox row + raw .eml in object storage), return 200, then async parse → attachments → ClamAV/allowlist → pipeline. Idempotency key = `Message-ID` + recipient.
4. Alerting: webhook 5xx rate, Worker `EXCEEDED_CPU`/failure counts in Workers logs, Email Routing activity log for `Delivery failed`.

**Upgrade path (in trigger order):**

- **Parsing gets heavy or handlers flake (CPU)** → Workers Paid $5/mo (30 s CPU) — still far under any email-API pricing.
- **Need guaranteed delivery through app downtime** → Worker → Cloudflare Queues (+ R2 for raw archive) in front of the webhook; same MX, same domain, no migration.
- **Need an SLA / leave Cloudflare** → Amazon SES receiving (S3 → Lambda → webhook; ~$0.10/1k, i.e. under $1/mo at 5k emails) or ImprovMX Premium $9/mo if we'd rather buy a managed parser. MX swap is a one-DNS-record migration *because* the Python side already parses raw MIME.
- **Later, outbound** (outreach drafts): note that Cloudflare Email *Sending* entered public beta April 2026 (Workers Paid, 3k/mo included then $0.35/1k) — a natural first stop before Resend/Postmark when that ticket lands.

**Explicitly rejected for v1:** self-hosted VPS receiver (fails $0 line via Oracle's port-25 block; worst ops burden for a core path) and any paid inbound API (violates the map's constraint; re-decide at the upgrade triggers above).

---

## Sources (checked 2026-10-21)

- Cloudflare Email Service docs — [Limits](https://developers.cloudflare.com/email-service/platform/limits/), [Pricing](https://developers.cloudflare.com/email-service/platform/pricing/), [Workers API (email handler)](https://developers.cloudflare.com/email-service/api/route-emails/email-handler/), [Spam filtering example](https://developers.cloudflare.com/email-service/examples/email-routing/spam-filtering/)
- Cloudflare changelog — [Queues on Workers Free plan (Feb 2026)](https://developers.cloudflare.com/changelog/post/2026-02-04-queues-free-plan/), [Email Sending public beta (Apr 2026)](https://developers.cloudflare.com/changelog/post/2026-04-16-email-sending-public-beta/), [Cloudflare Email Service announcement](https://blog.cloudflare.com/email-service/)
- Workers pricing (100k req/day, 10 ms CPU free): [developers.cloudflare.com/workers/platform/pricing](https://developers.cloudflare.com/workers/platform/pricing/)
- ImprovMX — [Webhooks guide](https://improvmx.com/guides/webhooks/) (retries, static IP), [Pricing](https://improvmx.com/pricing) (webhooks = Premium $9/mo), [Sending/receiving limits](https://improvmx.com/guides/sending-receiving-limits)
- Multipath routing / failure handling pattern: D. Więckiewicz, ["When things start to fail… Cloudflare Email Routing"](https://dariusz.wieckiewicz.org/en/when-things-start-to-fail-cloudflare-email-routing/) (updated Mar 2026) + linked Cloudflare community threads; Gmail 451 4.7.650 incident (Mar 2024)
- Cloudflare outage history: [18 Nov 2025 (~6 h, incl. Email Routing)](https://blog.cloudflare.com/18-november-2025-outage), [5 Dec 2025](https://blog.cloudflare.com/5-december-2025-outage), [status](https://www.cloudflarestatus.com/)
- VPS SMTP port policies: Oracle docs ([outbound 25 blocked for tenancies after Jun 2021](https://docs.oracle.com/iaas/releasenotes/changes/f7e95770-9844-43db-916c-6ccbaf2cfe24/index.htm)) + community reports of refusal to reopen; DigitalOcean/Hetzner outbound-25 blocks with inbound 25 open (serverfault/community threads)
- Managed inbound landscape 2026: [Pingram comparison of inbound email APIs (Feb 2026)](https://www.pingram.io/blog/best-inbound-email-notification-apis) (Mailtrap 4k/mo free, Pingram 3k/mo free, Resend/SendGrid/Mailgun/Postmark pricing); [Amazon SES pricing](https://aws.amazon.com/ses/pricing/) ($0.10/1k received); [Forward Email FAQ](https://forwardemail.net/en/faq) (free = forwarding only)
- maddy mail server (actively maintained): [maddy.email](https://maddy.email/)
