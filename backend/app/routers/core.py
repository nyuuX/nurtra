"""Core CRUD endpoints: profile/TDEE, food search, meal + exercise logs.

Every endpoint resolves the caller via session cookie (or bearer token).
Logged-in users read/write their own slice; anonymous users fall back to
the shared demo data so the app works before signup.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import nutrition
from ..data_context import DataContext, from_request, require_user
from ..foods import EXERCISE_LIST, FOODS, high_volume_foods, search_foods

router = APIRouter()

MEAL_ORDER = ["breakfast", "lunch", "dinner", "snack"]
MEAL_LABELS = {
    "breakfast": "Makan Pagi",
    "lunch": "Makan Siang",
    "dinner": "Makan Malam",
    "snack": "Camilan",
}


# ---- Profile / TDEE ---------------------------------------------------

def _validate_profile(body: dict) -> dict:
    gender = (body.get("gender") or "male").lower()
    if gender not in ("male", "female"):
        gender = "male"
    return {
        "name": str(body.get("name") or "Pengguna Nurtra")[:60],
        "gender": gender,
        "age": max(10, min(int(body.get("age") or 25), 100)),
        "weight_kg": max(30.0, min(float(body.get("weight_kg") or 70), 300)),
        "height_cm": max(100, min(float(body.get("height_cm") or 170), 250)),
        "activity": body.get("activity") or "moderate",
        "weekly_loss_kg": max(0.0, min(float(body.get("weekly_loss_kg") or 0.5), 2.0)),
        "body_fat_pct": body.get("body_fat_pct"),
        "fasting_protocol": body.get("fasting_protocol") or None,
    }


def _profile_view(ctx: DataContext) -> dict:
    profile = ctx.get_profile()
    merged = nutrition.nutrition_profile(
        profile.get("gender", "male"),
        profile.get("age", 25),
        profile.get("weight_kg", 70),
        profile.get("height_cm", 170),
        profile.get("activity", "moderate"),
        profile.get("weekly_loss_kg", 0.5),
        profile.get("body_fat_pct"),
        profile.get("fasting_protocol"),
    )
    return {"profile": profile, **merged}


@router.get("/profile")
def get_profile(request: Request) -> dict:
    return _profile_view(from_request(request))


@router.post("/profile")
def save_profile(
    body: dict, request: Request, _email: str = Depends(require_user)
) -> dict:
    ctx = from_request(request)
    ctx.set_profile(_validate_profile(body))
    return _profile_view(ctx)


# ---- Foods -----------------------------------------------------------

@router.get("/foods/search")
def food_search(
    request: Request,
    q: str,
    limit: int = 12,
    _email: str = Depends(require_user),
) -> dict:
    results = search_foods(q, limit=limit)
    from_request(request).push_recent_search(q)
    return {"query": q, "count": len(results), "foods": results}


@router.get("/foods")
def list_foods(category: str | None = None, limit: int = 100) -> dict:
    foods = FOODS
    if category:
        foods = [f for f in foods if f["category"] == category]
    return {"count": len(foods), "foods": foods[:limit]}


@router.get("/foods/volume")
def volume_foods(limit: int = 20) -> dict:
    """High-volume / low-kcal picks for hunger management (feature #4)."""
    picks = high_volume_foods(limit)
    return {"count": len(picks), "foods": picks}


@router.get("/exercises")
def list_exercises() -> dict:
    return {"count": len(EXERCISE_LIST), "exercises": EXERCISE_LIST}


# ---- Day / dashboard --------------------------------------------------

def _summarise(profile: dict, day: dict) -> dict:
    totals = nutrition.day_kcal(day)
    prof = nutrition.nutrition_profile(
        profile.get("gender", "male"),
        profile.get("age", 25),
        profile.get("weight_kg", 70),
        profile.get("height_cm", 170),
        profile.get("activity", "moderate"),
        profile.get("weekly_loss_kg", 0.5),
        profile.get("body_fat_pct"),
    )
    target = prof["target_kcal"]
    food_kcal = totals["kcal"]
    exercise_kcal = totals["exercise"]
    remaining = round(target - food_kcal + exercise_kcal)

    macro_targets = prof["macros"]
    eaten = {"protein": totals["protein"], "carb": totals["carb"], "fat": totals["fat"]}

    # Hero ring breakdown: Target - Makanan + Olahraga
    return {
        "date": day.get("date"),
        "target_kcal": target,
        "food_kcal": round(food_kcal),
        "exercise_kcal": round(exercise_kcal),
        "remaining_kcal": remaining,
        "net_kcal": round(food_kcal - exercise_kcal),
        "over": remaining < 0,
        "macros": {
            k: {
                "eaten_g": round(v, 1),
                "target_g": macro_targets[k]["target_g"],
                "pct": round(v / macro_targets[k]["target_g"] * 100, 1)
                if macro_targets[k]["target_g"]
                else 0.0,
            }
            for k, v in eaten.items()
        },
        "fasting": nutrition.fasting_status_for(profile.get("fasting_protocol"))
        if profile.get("fasting_protocol")
        else {"enabled": False},
        "meals": [
            {
                "key": key,
                "label": MEAL_LABELS[key],
                "items": [m for m in day.get("meals", []) if m.get("meal") == key],
                "kcal": round(
                    sum(m["kcal"] for m in day.get("meals", []) if m.get("meal") == key)
                ),
            }
            for key in MEAL_ORDER
        ],
        "exercises": day.get("exercises", []),
    }


@router.get("/today")
def get_today(request: Request) -> dict:
    ctx = from_request(request)
    db = ctx.load()
    day = ctx.get_or_create_day(db, _today_iso())
    return _summarise(ctx.get_profile(), day)


@router.get("/days/{date}")
def get_day(date: str, request: Request) -> dict:
    ctx = from_request(request)
    day = ctx.find_day(date)
    if day is None:
        raise HTTPException(404, f"Tidak ada data untuk tanggal {date}")
    return _summarise(ctx.get_profile(), day)


# ---- Meal entries -----------------------------------------------------

def _validate_meal_entry(body: dict, meal: str) -> dict:
    kcal = float(body.get("kcal") or 0)
    if kcal <= 0:
        raise HTTPException(422, "kcal wajib > 0")
    return {
        "id": body.get("id") or uuid.uuid4().hex[:8],
        "name": str(body.get("name") or "Makanan")[:80],
        "meal": meal,
        "kcal": round(kcal, 1),
        "protein_g": round(float(body.get("protein_g") or 0), 1),
        "carb_g": round(float(body.get("carb_g") or 0), 1),
        "fat_g": round(float(body.get("fat_g") or 0), 1),
        "portion_g": int(body.get("portion_g") or 100),
        "servings": float(body.get("servings") or 1.0),
        "volume_eating": bool(body.get("volume_eating")),
        "time": body.get("time") or datetime.now(timezone.utc).strftime("%H:%M"),
    }


@router.post("/meals/{meal}")
def add_meal(
    meal: str,
    body: dict,
    request: Request,
    _email: str = Depends(require_user),
) -> dict:
    if meal not in MEAL_ORDER:
        raise HTTPException(422, f"Meal harus salah satu dari: {', '.join(MEAL_ORDER)}")

    ctx = from_request(request)
    db = ctx.load()
    day = ctx.get_or_create_day(db, _today_iso())
    day["meals"].append(_validate_meal_entry(body, meal))
    ctx.save(db)
    return _summarise(ctx.get_profile(), day)


@router.delete("/meals/{meal}/{entry_id}")
def delete_meal(
    meal: str,
    entry_id: str,
    request: Request,
    _email: str = Depends(require_user),
) -> dict:
    ctx = from_request(request)
    db = ctx.load()
    day = ctx.get_or_create_day(db, _today_iso())
    before = len(day["meals"])
    day["meals"] = [
        m
        for m in day["meals"]
        if not (m.get("id") == entry_id and m.get("meal") == meal)
    ]
    if len(day["meals"]) == before:
        raise HTTPException(404, "Entri makanan tidak ditemukan")
    ctx.save(db)
    return _summarise(ctx.get_profile(), day)


# ---- Exercises --------------------------------------------------------

@router.post("/exercises")
def add_exercise(
    body: dict, request: Request, _email: str = Depends(require_user)
) -> dict:
    ctx = from_request(request)
    db = ctx.load()
    day = ctx.get_or_create_day(db, _today_iso())
    day["exercises"].append(
        {
            "id": body.get("id") or uuid.uuid4().hex[:8],
            "name": str(body.get("name") or "Olahraga")[:60],
            "kcal": round(float(body.get("kcal") or 0), 1),
            "duration_min": int(body.get("duration_min") or 30),
            "time": body.get("time") or datetime.now(timezone.utc).strftime("%H:%M"),
        }
    )
    ctx.save(db)
    return _summarise(ctx.get_profile(), day)


@router.delete("/exercises/{entry_id}")
def delete_exercise(
    entry_id: str,
    request: Request,
    _email: str = Depends(require_user),
) -> dict:
    ctx = from_request(request)
    db = ctx.load()
    day = ctx.get_or_create_day(db, _today_iso())

    # Match by id; older rows that predate the id field fall back to name.
    target = None
    for ex in day.get("exercises", []):
        if ex.get("id") and ex["id"] == entry_id:
            target = ex
            break
        if not ex.get("id") and entry_id in (ex.get("name"), f"noname-{ex.get('kcal')}"):
            target = ex
            break

    if target is None:
        raise HTTPException(404, "Entri latihan tidak ditemukan")

    day["exercises"] = [e for e in day["exercises"] if e is not target]
    ctx.save(db)
    return _summarise(ctx.get_profile(), day)


# ---- Weight -----------------------------------------------------------

@router.post("/weight")
def log_weight(
    body: dict, request: Request, _email: str = Depends(require_user)
) -> dict:
    weight = float(body.get("weight_kg") or 0)
    if not (30.0 <= weight <= 300.0):
        raise HTTPException(422, "Berat badan harus antara 30 dan 300 kg")

    ctx = from_request(request)
    db = ctx.load()
    day = ctx.get_or_create_day(db, _today_iso())
    day["weight_kg"] = weight

    # Also update the profile weight so TDEE recalculates
    profile = ctx.get_profile()
    profile["weight_kg"] = weight
    ctx.set_profile(profile)
    return {"ok": True, "weight_kg": weight, "date": day["date"]}


# ---- Favorites --------------------------------------------------------

@router.get("/favorites")
def list_favorites(request: Request) -> dict:
    favs = from_request(request).get_favorites()
    return {"count": len(favs), "favorites": favs}


@router.post("/favorites")
def add_favorite(
    body: dict, request: Request, _email: str = Depends(require_user)
) -> dict:
    fav = {
        "id": body.get("id") or uuid.uuid4().hex[:8],
        "name": str(body.get("name") or "Menu Favorit")[:80],
        "kcal": round(float(body.get("kcal") or 0), 1),
        "protein_g": round(float(body.get("protein_g") or 0), 1),
        "carb_g": round(float(body.get("carb_g") or 0), 1),
        "fat_g": round(float(body.get("fat_g") or 0), 1),
        "ingredients": body.get("ingredients") or [],
    }
    from_request(request).add_favorite(fav)
    return {"ok": True, "favorite": fav}


@router.delete("/favorites/{fav_id}")
def delete_favorite(
    fav_id: str, request: Request, _email: str = Depends(require_user)
) -> dict:
    if not from_request(request).delete_favorite(fav_id):
        raise HTTPException(404, "Favorit tidak ditemukan")
    return {"ok": True}


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()
