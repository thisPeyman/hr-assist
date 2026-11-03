# Netlify frontend and Railway backend

> For the current free-hosting path, use [Render + Neon](deployment-render-neon.md).
> The Railway notes below are retained for the older setup and are not required
> for the Render deployment.

Frontend production URL: https://hr-assist-137132cc.netlify.app
Netlify site ID: `1e841b4a-ede2-4201-b3a4-d20fd30087f9`.

For the current temporary arrangement using this computer as the backend host,
see [temporary hosting](temporary-hosting.md). Railway remains a separate,
not-yet-deployed production option.

## Backend

Run Railway deployment commands from `backend/`, which contains the Dockerfile,
Railway configuration, and upload exclusions. For a Git-backed service, set the
service root directory to `backend`. The container installs Python 3.14, locked
production dependencies, and Persian/English OCR tools. It starts FastAPI on
Railway's `PORT` as a non-root user. Railway runs `alembic upgrade head` before
starting each deployment; a failed migration prevents rollout.

Provision PostgreSQL with **pgvector and pg_trgm available** before migration.
The existing migration 0008 deliberately rejects PostgreSQL without pgvector.
Use a dedicated database for this application, not a shared database: migrations
create the `hr_app` role and revoke public schema privileges.

Set these service variables through Railway, never in committed files:

- `HR_MIGRATION_DATABASE_URL`: schema-owner connection, using
  `postgresql+asyncpg://...` and the Railway database hostname.
- `HR_APP_DB_PASSWORD`: a generated production password. Migration 0002 sets
  the `hr_app` database role password from this variable.
- `HR_APP_DATABASE_URL`: connection to the same database as `hr_app`, with
  that generated password, using `postgresql+asyncpg://...`. URL-encode password
  characters if constructing a URL manually. Never use the schema owner as
  the runtime connection; tenant isolation depends on the restricted role.
- `HR_COOKIE_SECURE=true`.
- `HR_RESET_PASSWORD_TOKEN_SECRET` and `HR_VERIFICATION_TOKEN_SECRET`: separate,
  generated production secrets.
- `HR_RESUME_AI_PROVIDER=groq` and `HR_GROQ_API_KEY`: the configured provider
  and its key, transferred through secret variables without printing values.
- `HR_RESUME_EXTRACT_MODEL` and `HR_RESUME_EXTRACT_MODEL_ESCALATION`: the model
  names verified against the provider account. Summaries use the extraction
  model unless `HR_RESUME_SUMMARY_MODEL` is explicitly set.

Do not upload `backend/.env`. Its database connections point to the local
computer and are unsuitable for Railway. The Dockerfile copies an explicit
allowlist, `.dockerignore` limits the build context, and `.railwayignore`
excludes secrets and local data from CLI uploads.

Original uploaded resumes are stored in PostgreSQL. Email attachment staging
requires a persistent volume at `/app/.data` or configured S3 storage. Inbound
email additionally requires a configured domain, webhook secret, and malware
scanner with current signatures; this container alone does not configure them.
AI candidate-query parsing and embeddings have separate `HR_SEARCH_*` settings;
see [candidate search](candidate-search.md). Resume AI configuration alone does
not enable semantic search.

## Connect Netlify

After the backend has a verified public HTTPS domain, add these rewrites to
`frontend/public/_redirects` **before** the existing SPA fallback. Replace
`BACKEND_HOST` with that actual domain; do not deploy the placeholder:

```text
/auth/* https://BACKEND_HOST/auth/:splat 200!
/api/* https://BACKEND_HOST/api/:splat 200!
/healthz https://BACKEND_HOST/healthz 200!
/* /index.html 200
```

The browser continues to use the Netlify origin for API calls and session
cookies. No frontend API key or cross-origin credential change is needed.
Build and publish only `frontend/dist` to the existing Netlify site.

## Acceptance checks

Verify `/healthz` returns JSON and `/api/me` returns JSON with HTTP 401 while
signed out. A static HTML fallback is not an API success. Then verify signup,
login, session persistence, and logout through the Netlify origin. A newly
provisioned production database has no local user accounts; create the account
through signup unless a separate data migration is explicitly requested.

Upload a synthetic resume, inspect its terminal parsing status and extracted
profile, then request an AI summary. These checks must run against the deployed
backend, not just the local provider client. Do not report production AI as
working until they pass.

The local Docker build requires Docker, which was not available in the current
development environment at preparation time. Railway build and end-to-end
acceptance remain pending authentication and actual deployment.
