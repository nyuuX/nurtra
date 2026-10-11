"""Atria Dawn AI endpoints: food parsing, weekly insights, recipes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from .. import ai_insights, ai_parse, ai_recipes
from ..config import get_settings
from ..data_context import require_user

router = APIRouter()
settings = get_settings()


@router.get("/status")
def ai_status() -> dict:
    """Which backend the AI features will use (atria vs local demo data)."""
    return {
        "mode": settings.ai_mode,
        "atria_ready": settings.atria_ready,
        "model": settings.atria_model,
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
