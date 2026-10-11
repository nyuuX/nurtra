"""Core CRUD endpoints: profile/TDEE, food search, meal + exercise logs.

Every endpoint resolves the caller via session cookie (or bearer token).
Logged-in users read/write their own slice; anonymous users fall back to
the shared demo data so the app works before signup.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import nutrition
from ..config import local_now, today_local_iso
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
    # Exercise calories are NOT credited back into the daily allowance.
    # The remaining quota is purely Target - Makanan so a workout cannot be
    # "eaten back"; burned calories are surfaced separately for information.
    remaining = round(target - food_kcal)

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
                "items": _group_items(
                    [m for m in day.get("meals", []) if m.get("meal") == key]
                ),
                "kcal": round(
                    sum(m["kcal"] for m in day.get("meals", []) if m.get("meal") == key)
                ),
            }
            for key in MEAL_ORDER
        ],
        "exercises": day.get("exercises", []),
        "water_ml": round(sum(e.get("ml", 0) for e in day.get("waters", []))),
        "water_target_ml": nutrition.water_target(profile),
        "waters": day.get("waters", []),
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


def _group_items(items: list[dict]) -> list[dict]:
    """Split a meal's entries into named groups.

    Entries with no group stay as flat items (backwards compatible with all
    existing logs). Grouped entries collapse into a single row carrying the
    group's own id, so the frontend can delete/rename a whole group at once.
    """
    groups: dict[str, dict] = {}
    for it in items:
        name = it.get("group")
        if not name:
            continue
        if name not in groups:
            groups[name] = {
                "id": "grp-" + uuid.uuid4().hex[:8],
                "name": name,
                "group": name,
                "is_group": True,
                "meal": it.get("meal"),
                "kcal": 0.0,
                "protein_g": 0.0,
                "carb_g": 0.0,
                "fat_g": 0.0,
                "items": [],
            }
        g = groups[name]
        g["kcal"] += it.get("kcal", 0)
        g["protein_g"] += it.get("protein_g", 0)
        g["carb_g"] += it.get("carb_g", 0)
        g["fat_g"] += it.get("fat_g", 0)
        g["items"].append(it)

    # Preserve the original ordering: a group renders where its first member
    # appeared, so adding to a group doesn't jump the row around. Entries
    # without a group stay as flat rows exactly where they were.
    out: list[dict] = []
    seen: set[str] = set()
    for it in items:
        name = it.get("group")
        if not name:
            out.append(it)
        elif name not in seen:
            seen.add(name)
            g = groups[name]
            out.append(
                {
                    **g,
                    "kcal": round(g["kcal"], 1),
                    "protein_g": round(g["protein_g"], 1),
                    "carb_g": round(g["carb_g"], 1),
                    "fat_g": round(g["fat_g"], 1),
                }
            )
    return out


def _validate_meal_entry(body: dict, meal: str) -> dict:
    kcal = float(body.get("kcal") or 0)
    if kcal <= 0:
        raise HTTPException(422, "kcal wajib > 0")
    # Optional group name. Empty/whitespace normalises to None so entries
    # stay flat unless the user actually names a group.
    group = str(body.get("group") or "").strip()[:60] or None
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
        "time": body.get("time") or local_now().strftime("%H:%M"),
        "group": group,
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


@router.delete("/meals/{meal}/group/{group_name}")
def delete_group(
    meal: str,
    group_name: str,
    request: Request,
    _email: str = Depends(require_user),
) -> dict:
    """Remove every entry in a named group (feature: user-named meal groups)."""
    ctx = from_request(request)
    db = ctx.load()
    day = ctx.get_or_create_day(db, _today_iso())
    before = len(day["meals"])
    day["meals"] = [
        m
        for m in day["meals"]
        if not (m.get("meal") == meal and m.get("group") == group_name)
    ]
    if len(day["meals"]) == before:
        raise HTTPException(404, "Grup tidak ditemukan")
    ctx.save(db)
    return _summarise(ctx.get_profile(), day)


@router.patch("/meals/{meal}/group/{group_name}")
def rename_group(
    meal: str,
    group_name: str,
    body: dict,
    request: Request,
    _email: str = Depends(require_user),
) -> dict:
    """Rename a group in place. Entries keep their per-item data; only the
    grouping label moves, and the frontend re-collapses them on the next
    /today fetch."""
    new_name = str(body.get("name") or "").strip()[:60]
    if not new_name:
        raise HTTPException(422, "Nama grup wajib diisi")

    ctx = from_request(request)
    db = ctx.load()
    day = ctx.get_or_create_day(db, _today_iso())

    if new_name == group_name:
        # No-op: still return the summary so the UI state round-trips.
        return _summarise(ctx.get_profile(), day)

    found = False
    for m in day["meals"]:
        if m.get("meal") == meal and m.get("group") == group_name:
            m["group"] = new_name
            found = True
    if not found:
        raise HTTPException(404, "Grup tidak ditemukan")
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
            "time": body.get("time") or local_now().strftime("%H:%M"),
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


# ---- Water -------------------------------------------------------------


def _water_entry(body: dict) -> dict:
    """One drink: an amount in ml plus when it was logged."""
    ml = float(body.get("ml") or 0)
    if ml <= 0 or ml > 3000:
        raise HTTPException(422, "Jumlah air harus antara 1 dan 3000 ml")
    return {
        "id": body.get("id") or uuid.uuid4().hex[:8],
        "ml": round(ml, 1),
        "time": (body.get("time") or local_now().strftime("%H:%M")),
        # Only label the source when the caller sends one, so the log stays
        # uncluttered for quick taps on a glass button.
        "label": str(body.get("label") or "")[:40],
    }


@router.post("/water")
def add_water(
    body: dict, request: Request, _email: str = Depends(require_user)
) -> dict:
    """Log a drink. Returns the day summary so the ring and totals update."""
    ctx = from_request(request)
    db = ctx.load()
    day = ctx.get_or_create_day(db, _today_iso())
    day.setdefault("waters", []).append(_water_entry(body))
    ctx.save(db)
    return _summarise(ctx.get_profile(), day)


@router.delete("/water/{entry_id}")
def delete_water(
    entry_id: str, request: Request, _email: str = Depends(require_user)
) -> dict:
    ctx = from_request(request)
    db = ctx.load()
    day = ctx.get_or_create_day(db, _today_iso())
    waters = day.get("waters", [])
    day["waters"] = [w for w in waters if w.get("id") != entry_id]
    if len(day["waters"]) == len(waters):
        raise HTTPException(404, "Catatan air tidak ditemukan")
    ctx.save(db)
    return _summarise(ctx.get_profile(), day)


@router.post("/water/reset")
def reset_water(
    request: Request, _email: str = Depends(require_user)
) -> dict:
    """Clear all of today's water log in one call."""
    ctx = from_request(request)
    db = ctx.load()
    day = ctx.get_or_create_day(db, _today_iso())
    day["waters"] = []
    ctx.save(db)
    return _summarise(ctx.get_profile(), day)


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
    # Local time, not UTC: a new log day begins at 00:00 local (07:00 UTC).
    return today_local_iso()
