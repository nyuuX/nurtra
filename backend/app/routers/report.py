"""Weekly report endpoints (feature #6)."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import nutrition
from ..data_context import DataContext, from_request, require_user

router = APIRouter()


def _week_boundaries(weeks_back: int) -> tuple[date, date]:
    today = date.today()
    end = today - timedelta(days=weeks_back * 7)
    start = end - timedelta(days=6)
    return start, end


def _by_date(days: list[dict]) -> dict[str, dict]:
    return {d["date"]: d for d in days if d.get("date")}


def week_payload(ctx: DataContext, weeks_back: int = 0) -> dict:
    start, end = _week_boundaries(weeks_back)
    days_map = _by_date(ctx.user_data(ctx.load()).get("days", []))
    profile = ctx.get_profile()

    target = nutrition.nutrition_profile(
        profile.get("gender", "male"),
        profile.get("age", 25),
        profile.get("weight_kg", 70),
        profile.get("height_cm", 170),
        profile.get("activity", "moderate"),
        profile.get("weekly_loss_kg", 0.5),
        profile.get("body_fat_pct"),
    )
    target_kcal = target["target_kcal"]
    protein_target = target["macros"]["protein"]["target_g"]

    bars = []
    weights = []
    total_intake = 0.0
    total_protein = 0.0
    counted = 0
    logged_days = 0

    cursor = start
    while cursor <= end:
        iso = cursor.isoformat()
        day = days_map.get(iso)
        totals = nutrition.day_kcal(day) if day else None
        intake = totals["kcal"] if totals else 0.0
        if totals:
            logged_days += 1
        bars.append(
            {
                "date": iso,
                "label": cursor.strftime("%a")[:3],
                "intake": round(intake),
                "target": round(target_kcal),
                "exercise": round(totals["exercise"]) if totals else 0,
            }
        )
        if totals:
            total_intake += intake
            total_protein += totals["protein"]
            counted += 1
        if day and day.get("weight_kg"):
            weights.append({"date": iso, "weight_kg": day["weight_kg"]})
        cursor += timedelta(days=1)

    trend = nutrition.weight_trend(weights) if weights else None
    plateau = nutrition.detect_plateau(weights) if weights else None

    return {
        "range": {"start": start.isoformat(), "end": end.isoformat(), "weeks_back": weeks_back},
        "target_kcal": round(target_kcal),
        "bars": bars,
        "weights": weights,
        "weight_trend": trend,
        "plateau": plateau,
        "stats": {
            "adherence": nutrition.adherence_for_week(
                [b for b in bars if b["intake"] > 0], target_kcal
            ),
            "avg_kcal": round(total_intake / counted) if counted else 0,
            "avg_protein_g": round(total_protein / counted, 1) if counted else 0,
            "logged_days": logged_days,
            "protein_target_g": round(protein_target, 1),
        },
    }


@router.get("/report")
def weekly_report(
    request: Request,
    weeks_back: int = 0,
    _email: str = Depends(require_user),
) -> dict:
    if weeks_back < 0 or weeks_back > 12:
        raise HTTPException(422, "weeks_back harus antara 0 dan 12")
    return week_payload(from_request(request), weeks_back)
