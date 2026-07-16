"""FastAPI app — M0: /health y /version. Sin lógica de negocio."""
from fastapi import FastAPI

from . import __version__
from .config import load_settings
from .db import check_db

app = FastAPI(title="VIOS Engine", version=__version__)


@app.get("/version")
async def version() -> dict:
    return {"service": "vios-engine", "version": __version__}


@app.get("/health")
async def health() -> dict:
    settings = load_settings()
    db_ok = await check_db(settings.database_url)
    return {
        "status": "ok" if db_ok else "degraded",
        "version": __version__,
        "deps": {"db": "ok" if db_ok else "down", "storage": "unchecked"},
    }
