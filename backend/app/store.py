"""MongoDB-backed store with in-memory caching and certifi SSL support.

Fixes Windows SSL handshake issues with MongoDB Atlas.
"""

from __future__ import annotations

import json
import threading
from datetime import timedelta
from pathlib import Path

from pymongo import MongoClient
import certifi

from .config import local_now, today_local_iso, get_settings

_lock = threading.Lock()
_client_cache = None
_mem_cache: dict | None = None


def _get_db():
    global _client_cache
    if _client_cache is None:
        settings = get_settings()
        uri = (settings.mongodb_uri or "").strip()
        if not (uri.startswith("mongodb://") or uri.startswith("mongodb+srv://")):
            raise RuntimeError(
                "MONGODB_URI is missing or malformed. It must start with "
                "'mongodb://' or 'mongodb+srv://'. Current value: "
                f"{uri!r}. Set the MONGODB_URI environment variable "
                "(Vercel: Settings > Environment Variables) to your Atlas "
                "connection string."
            )
        _client_cache = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            tlsCAFile=certifi.where(),
            tls=True,
            tlsAllowInvalidCertificates=True
        )
    settings = get_settings()
    return _client_cache[settings.db_name]


def _seed() -> dict:
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
                "meals": [{**m, "id": f"d{i}-{m['id']}"} for m in meals],
                "exercises": [{"id": f"e{i}", "name": "Jalan Cepat", "kcal": 150.0, "duration_min": 30}] if i % 2 == 0 else [],
                "weight_kg": weights[i],
            }
        )

    return {
        "_schema": 2,
        "profile": profile,
        "days": days,
        "favorites": [
            {"id": "fav1", "name": "Chicken Rice Bowl", "kcal": 520, "protein_g": 48.0, "carb_g": 55.0, "fat_g": 12.0, "ingredients": ["Dada Ayam Tanpa Kulit", "Nasi Merah", "Sawi Hijau"]},
            {"id": "fav2", "name": "Tempe Orek", "kcal": 250, "protein_g": 18.0, "carb_g": 12.0, "fat_g": 14.0, "ingredients": ["Tempe", "Bawang", "Cabai"]},
        ],
        "recent_searches": ["dada ayam", "nasi merah", "tempe"],
        "anonymous_dirty": False,
        "users": {},
    }


LOCAL_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "defisitku.json"

def _load_local() -> dict:
    if LOCAL_DB_PATH.exists():
        try:
            return json.loads(LOCAL_DB_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    data = _seed()
    _save_local(data)
    return data

def _save_local(data: dict) -> None:
    try:
        LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_DB_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def load() -> dict:
    global _mem_cache
    with _lock:
        if _mem_cache is not None:
            return _mem_cache

        try:
            db = _get_db()
            collection = db["app_state"]
            doc = collection.find_one({"_id": "main"})
            if not doc:
                data = _seed()
                collection.replace_one({"_id": "main"}, data, upsert=True)
                _mem_cache = data
                _save_local(data)
                return data
            doc.pop("_id", None)
            _mem_cache = doc
            _save_local(doc)
            return doc
        except Exception:
            # Fallback to local JSON if MongoDB is unreachable (e.g. IP allowlist block)
            data = _load_local()
            _mem_cache = data
            return data


def save(data: dict) -> None:
    global _mem_cache
    with _lock:
        _mem_cache = data
        payload = {"_id": "main", **data}
        db = _get_db()
        collection = db["app_state"]
        collection.replace_one({"_id": "main"}, payload, upsert=True)


def today_iso() -> str:
    return today_local_iso()
