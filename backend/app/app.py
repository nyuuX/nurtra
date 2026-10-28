"""Nurtra — calorie deficit tracker for the Indonesian palate.

Run:  uvicorn backend.app.app:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings

settings = get_settings()

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend" / "static"

app = FastAPI(
    title="Nurtra API",
    description="Penghitung kalori defisit + Atria Dawn AI",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "ai_mode": settings.ai_mode,
        "gemini_configured": bool(settings.gemini_api_key),
        "model": settings.gemini_model,
    }


# ---- Routers ---------------------------------------------------------
from .routers import ai, auth, core, report  # noqa: E402

app.include_router(core.router, prefix="/api", tags=["core"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(report.router, prefix="/api", tags=["report"])


# ---- Serve the frontend ----------------------------------------------
# Mounted last on purpose: everything not matched by the API falls through
# to the static frontend (index.html + dashboard + report), so the whole
# app runs on one port.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
