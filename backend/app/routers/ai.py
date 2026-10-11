"""Atria Dawn AI endpoints: food parsing, weekly insights, recipes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from .. import ai_insights, ai_parse, ai_photo, ai_recipes
from ..config import get_settings
from ..data_context import require_user

router = APIRouter()
settings = get_settings()
log = logging.getLogger("defisitku.ai")


@router.get("/status")
def ai_status() -> dict:
    """Which backend the AI features will use (gemini)."""
    return {
        "mode": "gemini",
        "gemini_ready": settings.gemini_ready,
        "model": settings.gemini_model,
        "photo_ready": settings.gemini_ready,
        "photo_model": settings.gemini_model,
    }


@router.post("/parse-foods")
def parse_foods(body: dict, _email: str = Depends(require_user)) -> dict:
    """Free-text food log -> structured meal entries (feature #2)."""
    text = str(body.get("text") or "")
    return ai_parse.parse_foods(text)


@router.post("/recipes")
def recipes(body: dict, _email: str = Depends(require_user)) -> dict:
    """High-protein recipe suggestions from pantry items (features #2/#4)."""
    return ai_recipes.suggest_recipes(
        pantry=body.get("pantry") or [],
        target_kcal=int(body.get("target_kcal") or 500),
        max_results=int(body.get("max_results") or 3),
    )


@router.post("/weekly-insights")
def weekly_insights(
    body: dict, request: Request, _email: str = Depends(require_user)
) -> dict:
    """7-day summary -> insights + recommendations (feature #6)."""
    from ..data_context import from_request

    ctx = from_request(request)
    week = body.get("week")
    if not week:
        # No payload supplied: derive it from this user's week on the server.
        from .report import week_payload

        week = week_payload(ctx, int(body.get("weeks_back") or 0))
    return ai_insights.weekly_insights(week)


# ---- Photo -> nutrition -----------------------------------------------------
# Atria Dawn is text-only, so this feature uses a separate vision provider
# (Gemini, OpenAI-compatible). Needs python-multipart for multipart uploads.

@router.post("/photo-foods")
async def photo_foods(
    request: Request,
    file: UploadFile = File(...),
    _email: str = Depends(require_user),
) -> dict:
    """Photo of a meal -> recognised foods with nutrition estimates.

    Returns {"foods": [...]} when confident, or {"candidates": [...]} when
    the model is unavailable — the frontend degrades to manual pick +
    portion, never to an error.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(422, "File gambar kosong")
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(422, "Ukuran gambar maksimal 12 MB")

    mime = (file.content_type or "image/jpeg").lower()
    if not mime.startswith("image/"):
        raise HTTPException(422, "File harus berupa gambar")

    # Hint from an optional accompanying filename, e.g. "nasi-padang.jpg".
    # The model is not told the filename, but a hint like "nasi padang"
    # steers it when the photo is ambiguous.
    hint = ""
    name = (file.filename or "").rsplit(".", 1)[0]
    hint = name.replace("-", " ").replace("_", " ").strip()[:60]
    try:
        return ai_photo.recognise_food(raw, mime, hint=hint)
    except Exception as exc:
        # recognise_food already degrades internally; reaching here means
        # something more basic broke. Never dead-end the feature.
        log.warning("photo recognition failed: %s", exc)
        return {
            "foods": [],
            "source": "error",
            "message": "Gagal memproses foto. Coba foto lain.",
        }
