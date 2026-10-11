"""Tiny JSON-file store. Single-user, zero-config, good enough for a local

demo. Swap this module for Postgres/Mongo without touching the routers.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

from .config import local_now, today_local_iso, get_settings

_lock = threading.Lock()


def _seed() -> dict:
    """First-run state: a demo profile and a few days of sample logs so the

    dashboard and weekly report render something meaningful immediately."""
    profile = {
        "name": "Pengguna Nurtra",
        "gender": "male",
        "age": 25,
        "weight_kg": 75.0,
        "height_cm": 175,
        "activity": "moderate",
        "weekly_loss_kg": 0.5,
        "body_fat_pct": None,
        "fasting_protocol": "16:8",
    }

    def day(meals, exercise_kcal=0.0, weight=None):
        return {
            "date": None,  # filled by _seed_week below
            "meals": meals,
            "exercises": [{"name": "Jalan Cepat", "kcal": exercise_kcal}] if exercise_kcal else [],
            "weight_kg": weight,
        }

    meal_a = [
        {"id": "m1", "name": "Nasi Merah", "meal": "lunch", "kcal": 320, "protein_g": 6.0, "carb_g": 68.0, "fat_g": 2.4, "portion_g": 200, "servings": 1.0, "time": "12:30"},
        {"id": "m2", "name": "Dada Ayam Tanpa Kulit", "meal": "lunch", "kcal": 248, "protein_g": 46.5, "carb_g": 0.0, "fat_g": 5.4, "portion_g": 150, "servings": 1.5, "time": "12:30"},
    ]
    meal_b = [
        {"id": "m3", "name": "Tempe", "meal": "dinner", "kcal": 193, "protein_g": 18.0, "carb_g": 9.0, "fat_g": 11.0, "portion_g": 100, "servings": 1.0, "time": "19:00"},
        {"id": "m4", "name": "Telur Ayam", "meal": "breakfast", "kcal": 155, "protein_g": 13.0, "carb_g": 1.1, "fat_g": 11.0, "portion_g": 60, "servings": 1.0, "time": "07:30"},
    ]

    today = local_now().date()
    days = []
    weights = [75.2, 75.0, 74.8, 75.1, 74.6, 74.5, 74.3]
    for i in range(7):
        d = today - timedelta(days=6 - i)
        meals = meal_a if i % 2 == 0 else meal_b
        if i == 6:
            meals = meal_a + meal_b
        days.append(
            {
                "date": d.isoformat(),
                "meals": [
                    {**m, "id": f"d{i}-{m['id']}"}
                    for m in meals
                ],
                # Exercises must carry an id: the DELETE endpoint matches on it.
                "exercises": [{"id": f"e{i}", "name": "Jalan Cepat", "kcal": 150.0, "duration_min": 30}] if i % 2 == 0 else [],
                "weight_kg": weights[i],
            }
        )

    return {
        "profile": profile,
        "days": days,
        "favorites": [
            {"id": "fav1", "name": "Chicken Rice Bowl", "kcal": 520, "protein_g": 48.0, "carb_g": 55.0, "fat_g": 12.0, "ingredients": ["Dada Ayam Tanpa Kulit", "Nasi Merah", "Sawi Hijau"]},
            {"id": "fav2", "name": "Tempe Orek", "kcal": 250, "protein_g": 18.0, "carb_g": 12.0, "fat_g": 14.0, "ingredients": ["Tempe", "Bawang", "Cabai"]},
        ],
        "recent_searches": ["dada ayam", "nasi merah", "tempe"],
    }


def _migrate_v1_to_anonymous(data: dict) -> dict:
    """v1 stored data at the top level (single user). Auth needs an explicit
    `users` table alongside it; the anonymous slice *is* those top-level keys,
    so we only have to add the table and bump the schema marker."""
    data.setdefault("users", {})
    data.setdefault("profile", {})
    data.setdefault("days", [])
    data.setdefault("favorites", [])
    data.setdefault("recent_searches", [])
    data["_schema"] = 2
    return data


def _seed_v2() -> dict:
    data = _seed()
    data["users"] = {}
    data["_schema"] = 2
    return data


def load() -> dict:
    path = Path(get_settings().db_path)
    with _lock:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            data = _seed_v2()
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return data
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # Corrupt file: reseed rather than crash the whole app
            data = _seed_v2()
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return data
        if data.get("_schema") != 2:
            data = _migrate_v1_to_anonymous(data)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data


def save(data: dict) -> None:
    path = Path(get_settings().db_path)
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)


def today_iso() -> str:
    # Local time, not UTC — the log day rolls over at 00:00 local.
    return today_local_iso()
