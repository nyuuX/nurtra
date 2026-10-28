"""Weekly report endpoints (feature #6)."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import nutrition
from ..config import local_now
from ..data_context import DataContext, from_request, require_user

router = APIRouter()


def _week_boundaries(weeks_back: int = 0) -> tuple[date, date]:
    # date.today() already resolves in local time; the report window and the
    # log day must use the same zone or the last bar drifts a day.
    today = local_now().date()
    end = today - timedelta(days=weeks_back * 7)
    start = end - timedelta(days=6)
    return start, end


def _by_date(days: list[dict]) -> dict[str, dict]:
    return {d["date"]: d for d in days if d.get("date")}


def _day_stats(
    ctx: DataContext,
    start: date,
    end: date,
    *,
    with_full_labels: bool = False,
) -> dict:
    """Shared window builder: per-day bars + aggregates over start..end."""
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
    total_water = 0.0
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

        bar = {
            "date": iso,
            "weekday": cursor.strftime("%a")[:3],
            "kcal": round(intake),
            "target_kcal": round(target_kcal),
            "exercise_kcal": round(totals["exercise"]) if totals else 0,
            "logged": bool(totals),
            "over": (intake > target_kcal) if totals else False,
        }
        if with_full_labels:
            # 30-day view needs unambiguous dates; the 7-day chart only
            # shows weekday initials.
            bar["date_label"] = cursor.strftime("%a, %d %b")
        bars.append(bar)

        if totals:
            total_intake += intake
            total_protein += totals["protein"]
            counted += 1
        if day and day.get("weight_kg"):
            weights.append({"date": iso, "weight_kg": day["weight_kg"]})

        # Water is tracked per day, so it is totalled in the same pass.
        total_water += (
            sum(w.get("ml", 0) for w in day.get("waters", [])) if day else 0.0
        )
        cursor += timedelta(days=1)

    return {
        "target_kcal": round(target_kcal),
        "protein_target_g": round(protein_target, 1),
        "bars": bars,
        "weights": weights,
        "weight_trend": nutrition.weight_trend(weights) if weights else None,
        "logged_days": logged_days,
        "avg_kcal": round(total_intake / counted) if counted else 0,
        "avg_protein_g": round(total_protein / counted, 1) if counted else 0,
        "avg_water_ml": round(total_water / counted) if counted else 0,
        "water_target_ml": nutrition.water_target(profile),
    }


def week_payload(ctx: DataContext, weeks_back: int = 0) -> dict:
    start, end = _week_boundaries(weeks_back)
    stats = _day_stats(ctx, start, end)
    bars = stats["bars"]
    target_kcal = stats["target_kcal"]

    today = local_now().date()
    h30_start = today - timedelta(days=29)
    h30_stats = _day_stats(ctx, h30_start, today, with_full_labels=True)

    return {
        "range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "weeks_back": weeks_back,
        },
        "target_kcal": target_kcal,
        "bars": bars,
        "history": {
            "range": {
                "start": h30_start.isoformat(),
                "end": today.isoformat(),
                "days": 30,
            },
            "target_kcal": h30_stats["target_kcal"],
            "bars": h30_stats["bars"],
            "weights": h30_stats["weights"],
            "weight_trend": h30_stats["weight_trend"],
            "stats": {
                "avg_kcal": h30_stats["avg_kcal"],
                "avg_protein_g": h30_stats["avg_protein_g"],
                "logged_days": h30_stats["logged_days"],
                "avg_water_ml": h30_stats["avg_water_ml"],
                "water_target_ml": h30_stats["water_target_ml"],
            },
        },
        "weights": stats["weights"],
        "weight_trend": stats["weight_trend"],
        "plateau": nutrition.detect_plateau(stats["weights"]) if stats["weights"] else None,
        "stats": {
            "adherence": nutrition.adherence_for_week(
                [b for b in bars if b["kcal"] > 0], target_kcal
            ),
            "avg_kcal": stats["avg_kcal"],
            "avg_protein_g": stats["avg_protein_g"],
            "logged_days": stats["logged_days"],
            "protein_target_g": stats["protein_target_g"],
            "avg_water_ml": stats["avg_water_ml"],
            "water_target_ml": stats["water_target_ml"],
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
