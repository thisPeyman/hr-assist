# 03 - Receiving inbound email on a build-not-buy stack

Type: research
Status: resolved

## Question

The app gets an `@app-domain` address users forward resumes to. Without paid inbound-email services, what are the realistic 2026 options for receiving that mail and triggering a Python webhook — self-hosted SMTP receiver (Postfix/maddy/etc. on a VPS), free-tier/borderline services (e.g. Cloudflare Email Routing → Worker → webhook), or something else? Compare reliability, deliverability, spam/attachment handling, and ops burden. Recommend one for v1 and note the upgrade path if volume grows.

## Context

- Build-not-buy constraint (map Notes): the OpenAI API is the only paid external dependency; free tiers of infra services are acceptable — judge where the line is.
- Feeds: the ingestion design in the spec (09).
- Findings go in `.scratch/hr-ai-assistant/research/`; link from the answer.

## Answer

**v1: Cloudflare Email Routing → thin Email Worker → HTTP POST of raw MIME to our Python webhook — $0, unlimited inbound.** Cloudflare folded Email Routing into its new "Email Service" (2026) but inbound remains free and uncapped; a single catch-all rule (`resumes+<companySlug>@jobs.app-domain`) routes to a ~20-line Worker that streams `message.raw` to our webhook and forwards a copy to a backup dead-drop mailbox. Keep the Worker a thin relay (free plan caps CPU at 10 ms/invocation) and parse MIME + attachments (ClamAV, type/size allowlist) in Python. Two real weaknesses — no app-level webhook retry and no managed spam filter — are patched with the community-standard "multipath" backup forward and slug-gated recipients + `setReject()`; provider outages self-heal because senders' MTAs retry for ~24–48 h.

**Rejected for v1:** self-hosted Postfix/maddy on a VPS (receiving works, but the only free VPS — Oracle — blocks port 25, so it means ~$5/mo plus the highest ops burden on a core ingestion path) and free-tier managed services (ImprovMX webhooks are $9/mo Premium-only; Mailtrap 4k/mo and Pingram 3k/mo are viable but volume-capped with vendor risk). **Upgrade path:** stay on Cloudflare — Queues/R2 for guaranteed delivery, $5/mo Workers Paid when parsing gets heavy — then Amazon SES receiving (~$0.10/1k) or a paid inbound API only if we outgrow free or need an SLA; the raw-MIME contract makes that a one-record MX swap.

Full comparison, limits, failure playbook, and sources: [research/03-inbound-email-options.md](../research/03-inbound-email-options.md)
