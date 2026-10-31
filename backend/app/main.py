"""App assembly."""

import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI

from app.candidate_profiles import router as candidate_profiles_router
from app.config import settings
from app.db import async_session_factory
from app.inbound import inbound_router
from app.parsing.llm import get_extractor
from app.parsing.worker import run_worker_forever
from app.pipeline import router as pipeline_router
from app.resumes import resumes_router
from app.review import review_router
from app.routes import api_router, auth_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Postgres-as-queue worker (spec §7.3): single uploads are processed
    # inline by the API for sub-minute UX; this loop drains everything else
    # (future email-in path, retries after crashes). Cancel on shutdown.
    worker = asyncio.create_task(
        run_worker_forever(async_session_factory, await get_extractor())
    )
    try:
        yield
    finally:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker


app = FastAPI(title="AI HR Assistant", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(api_router)
app.include_router(inbound_router)
app.include_router(review_router)
app.include_router(resumes_router)
app.include_router(candidate_profiles_router)
app.include_router(pipeline_router)


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


# Serve the built SPA when present (dev uses the Vite server + proxy).
_dist = Path(__file__).resolve().parent.parent / settings.frontend_dist
if _dist.is_dir():
    app.frontend("/", directory=str(_dist))
