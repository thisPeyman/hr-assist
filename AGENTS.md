## Agent skills

### Issue tracker

Issues are tracked as local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels are used as-is: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Frontend design

Always load the `frontend-design` skill before building or reshaping any UI/UX, so the work follows intentional visual design guidance rather than templated defaults.

always use standard question box to ask questions.

### Temporary public demo / deployment

Before deploying, restarting the public demo, changing its tunnel, or diagnosing online login/API failures, read `docs/agents/temporary-demo.md` completely. It records the verified setup and troubleshooting order. Reuse the existing Netlify site; never assume an old Quick Tunnel hostname is still valid. The user's selected setup is a Netlify frontend with local backend/PostgreSQL and Cloudflare only. This guide does not independently authorize public exposure or deployments outside the current user request.
