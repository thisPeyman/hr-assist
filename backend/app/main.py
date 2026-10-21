"""App assembly."""

from pathlib import Path

from fastapi import FastAPI

from app.config import settings
from app.routes import api_router, auth_router

app = FastAPI(title="AI HR Assistant", version="0.1.0")
app.include_router(auth_router)
app.include_router(api_router)


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


# Serve the built SPA when present (dev uses the Vite server + proxy).
_dist = Path(__file__).resolve().parent.parent / settings.frontend_dist
if _dist.is_dir():
    app.frontend("/", directory=str(_dist))
