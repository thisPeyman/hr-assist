# Render + Neon deployment

This project can run its FastAPI backend on Render's free web service while
using a PostgreSQL database hosted by Neon. The repository contains a Render
Blueprint at [`render.yaml`](../render.yaml); it builds `backend/Dockerfile`,
runs `alembic upgrade head` before each deployment, and checks `/healthz`.

## 1. Create the Neon database

Create a Neon project and database in a region close to the Render service
(the Blueprint uses Frankfurt). Neon must support the PostgreSQL extensions
required by migration `0008`: `vector` and `pg_trgm`. Copy the **pooled** and
**direct** connection strings from Neon and convert the scheme to
`postgresql+asyncpg://` for this application. Keep the direct/schema-owner URL
for `HR_MIGRATION_DATABASE_URL`; use a separate application URL for
`HR_APP_DATABASE_URL`.

The application URL must use the `hr_app` role created by migration `0002` and
the same password supplied as `HR_APP_DB_PASSWORD`. URL-encode special
characters in the password. Do not commit either URL.

For local development, keep using `backend/.env` with the local values from
`.env.example`:

```text
HR_MIGRATION_DATABASE_URL=postgresql+asyncpg://postgres:<local-password>@127.0.0.1:5432/hr_dev
HR_APP_DATABASE_URL=postgresql+asyncpg://hr_app:hr_app_dev@127.0.0.1:5432/hr_dev
```

`HR_MIGRATION_DATABASE_URL` is the privileged database connection used only by
Alembic migrations. `HR_APP_DATABASE_URL` is the restricted `hr_app` connection
used by the running API. Locally, migration `0002` creates `hr_app`; on Neon,
the same migration creates or updates it during the Render pre-deploy step.
The Render-shaped variable list is also in
[`backend/.env.render.example`](../backend/.env.render.example).

## 2. Create the Render service

In Render, choose **New → Blueprint**, connect this repository, and select the
branch to deploy. Render reads `render.yaml`. Set the three `sync: false`
values in the service environment:

- `HR_MIGRATION_DATABASE_URL`: Neon direct connection, schema-owner user.
- `HR_APP_DATABASE_URL`: Neon pooled connection as `hr_app`.
- `HR_GROQ_API_KEY`: the provider key, if resume AI is enabled.

The Blueprint generates `HR_APP_DB_PASSWORD` and the auth token secrets. If
you set the application URL manually, use that generated password. Never use
the schema-owner URL as the runtime application connection.

The free Render instance sleeps after inactivity, so the first request after
sleep can be slow. Its filesystem is ephemeral; configure S3-compatible
storage for durable inbound document staging before using email ingestion.

## 3. Connect the existing Netlify frontend

After Render reports a healthy HTTPS URL, replace the three tunnel targets in
`frontend/public/_redirects` with that Render hostname, then build and deploy
the existing Netlify site. Keep the rules before the SPA fallback:

```text
/auth/* https://BACKEND_HOST/auth/:splat 200!
/api/* https://BACKEND_HOST/api/:splat 200!
/healthz https://BACKEND_HOST/healthz 200!
/* /index.html 200
```

Do not put Neon credentials, Render environment values, or AI keys in the
frontend. The browser continues to call the Netlify origin and receives the
session cookie through the proxy.

## 4. Verify the deployment

Check that `GET /healthz` returns JSON `{"status":"ok"}`. While signed out,
`GET /api/me` must return JSON with HTTP 401 rather than the SPA HTML. Then
exercise signup, login, session persistence, logout, a synthetic resume upload,
and an AI summary from the Netlify origin.
