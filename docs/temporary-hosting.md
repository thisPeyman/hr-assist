# Temporary Netlify access to this computer

Canonical agent runbook (Persian): [temporary demo guide](agents/temporary-demo.md).
Read that guide first for the verified setup, restart procedure, and lessons learned.

The frontend at https://hr-assist-137132cc.netlify.app uses the backend and
PostgreSQL running on this Windows computer. This is temporary hosting, not a
cloud deployment of the backend or database.

## Current processes

- Normal local backend: `http://127.0.0.1:8000`.
- Backend dedicated to the public HTTPS tunnel: `http://127.0.0.1:8001`.
- Local frontend: `http://127.0.0.1:5173`.

The temporary backend is a separate Uvicorn process started with
`HR_COOKIE_SECURE=true` in its process environment. The local `.env` and normal
HTTP development session are unchanged. Both backends use the configured local
database and AI provider. No database port is published by the tunnel.

`frontend/public/_redirects` proxies `/auth/*`, `/api/*`, and `/healthz` to the
actual tunnel origin before applying the SPA fallback. API requests and session
cookies therefore remain on the Netlify origin in the browser. The tunnel
origin is public; the API's normal authentication and tenant isolation apply.

Logs and downloaded tunnel binaries are in the ignored `.scratch/runtime/`
directory. The public backend logs are `temporary-backend.stdout.log` and
`temporary-backend.stderr.log`. Tunnel logs use the `temporary-tunnel-` prefix.
Do not enable debug HTTP header logging: it can record session cookies.

## Lifetime

The computer must remain awake, connected to the internet, and running both
the public backend and tunnel. These processes were started in the background;
they do not automatically start again after reboot. `start.bat` starts the
ordinary local app only, not its public tunnel.

For the current manager demo, keep v2rayN's TUN mode enabled. Connectivity checks
after enabling TUN showed that QUIC works while HTTP/2 does not. The active
Cloudflare tunnel therefore uses `--protocol quic`; its log is
`.scratch/runtime/manager-demo-quic.log`. The current tunnel was launched in an
agent terminal session, which must also remain running. No localhost.run tunnel
was created; the setup uses only Cloudflare, as requested.

Restarting an account-free tunnel can change its public hostname. In that case,
verify the new `/healthz`, update the three proxy rules, build the frontend, and
deploy `frontend/dist` to the existing Netlify site. Do not put `.env`, database
URLs, or AI keys in the frontend build or proxy rules.

To end public access, stop the tunnel process using Task Manager or its verified
process ID. The normal local frontend/backend can continue running. Until the
Netlify proxy rules are changed or removed and redeployed, the online frontend
will report API connection errors after its tunnel is stopped.

## Verification and limitations

The smoke test in `.scratch/runtime/check_temporary_host.py` uses an isolated
synthetic account and organization; its generated credentials stay in the
ignored runtime directory. It verifies HTTPS cookies, signup, login, session
persistence, logout, resume extraction, and summary generation. It does not
change the user's existing account password or populate the user's organization.

Initial Cloudflare Quick Tunnel checks reached the real backend and successfully
processed AI requests, but HTTP/2 tunnel disconnections produced intermittent
502 responses, including while testing through Netlify. Do not describe this
connection as stable until the complete online smoke test passes. Quick Tunnels
also do not support SSE, which the candidate search UI uses. See
[Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

The credentials previously supplied for the user's account returned
`LOGIN_BAD_CREDENTIALS` locally. Restoring connectivity does not reset an
existing account password or create an account automatically.

## Verified manager demo

After enabling v2rayN TUN and switching Cloudflare to QUIC, the published Netlify
site passed login, secure session persistence, candidate profile and retained
AI summary retrieval, a completed search response, logout, and session
revocation. The AI summary model in the test workspace is `qwen/qwen3.8-27b`.
These checks establish the tested behavior, not a free-tunnel uptime guarantee
or a guarantee of incremental SSE delivery.

The isolated demo account's credentials are in the ignored local file
`.scratch/runtime/temporary-host-smoke-account.json`. It contains synthetic
candidate data only. Share the Netlify URL and, if desired, this demo account's
credentials with the reviewer; do not publish this credentials file in the
frontend or source repository.
