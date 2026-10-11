"""Feature #2 + #4: high-protein recipe suggestions from pantry items."""

from __future__ import annotations

import json
import logging

from .atria_client import chat, extract_json
from .config import get_settings
from .foods import FOODS

log = logging.getLogger("defisitku.recipes")
settings = get_settings()

RECIPE_SYSTEM = """Kamu adalah chef nutrisi untuk Nurtra. Buat rekomendasi resep praktis tinggi protein, cocok untuk orang Indonesia yang sedang defisit kalori.
Aturan:
- Gunakan bahan yang disebutkan pengguna (pantry) sebagai basis; tambahkan bahan umum (bumbu dapur, sayuran) bila perlu.
- Sajikan data nutrisi per porsi.
- volume_eating = true bila hidangan padat serat/air dan <400 kkal per porsi.
- Waktu masak maksimal 25 menit, alat dapur minimal.
- Output HANYA JSON valid, tanpa penjelasan."""

RECIPE_SCHEMA = {
    "recipes": [
        {
            "name": "nama resep",
            "kcal": "kkal per porsi",
            "protein_g": "gram protein",
            "carb_g": "gram karbohidrat",
            "fat_g": "gram lemak",
            "ingredients": ["bahan"],
            "steps": ["langkah"],
            "prep_min": "integer",
            "volume_eating": "boolean",
            "tags": ["tag"],
        }
    ]
}


def suggest_recipes(pantry: list[str], target_kcal: int = 500, max_results: int = 3) -> dict:
    """High-protein recipe suggestions from what the user has on hand."""
    pantry = [p.strip() for p in (pantry or []) if p and p.strip()]
    if not pantry:
        return {"recipes": [], "source": "empty", "confidence": 0.0}

    if settings.atria_ready:
        try:
            payload = {
                "pantry": pantry,
                "target_kcal_per_serving": target_kcal,
                "max_results": max_results,
                "schema": RECIPE_SCHEMA,
                "local_food_names": [f["name"] for f in FOODS[:40]],
            }
            content = chat(
                [
                    {"role": "system", "content": RECIPE_SYSTEM},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                temperature=0.6,
            )
            parsed = extract_json(content)
            if parsed and isinstance(parsed, dict) and parsed.get("recipes"):
                parsed["source"] = "atria"
                parsed["atria_raw"] = content
                return parsed
            log.info("suggest_recipes: no usable JSON from Atria, using local fallback")
        except Exception as exc:
            log.warning("suggest_recipes: Atria failed, using local fallback: %s", exc)

    return _local_recipes(pantry, max_results)


def _local_recipes(pantry: list[str], max_results: int) -> dict:
    """Deterministic fallback built from the local database."""
    have = {p.lower() for p in pantry}

    def has(*names: str) -> bool:
        return any(n.lower() in have for n in names)

    recipes: list[dict] = []
    if has("dada ayam", "ayam", "chicken breast") and has("nasi", "nasi merah"):
        recipes.append(_recipe("Chicken Rice Bowl Nurtra", ["Dada Ayam Tanpa Kulit", "Nasi Merah", "Sawi Hijau", "Wortel"]))
    if has("tempe", "tahu"):
        recipes.append(_recipe("Tempe Tahu Orak-Arik", ["Tempe", "Tahu", "Kangkung", "Tomat"]))
    if has("telur"):
        recipes.append(_recipe("Telur Dadar Sayur", ["Telur Ayam", "Kol", "Wortel"]))
    if has("ikan nila", "nila", "kembung", "tongkol", "ikan"):
        recipes.append(_recipe("Ikan Bakar Sambal Matah", ["Ikan Nila", "Tomat", "Paprika"]))
    if has("daging sapi", "sapi"):
        recipes.append(_recipe("Sapi Buncis", ["Daging Sapi", "Kol", "Wortel"]))

    return {
        "recipes": recipes[:max_results],
        "source": "local" if recipes else "none",
        "confidence": 0.5 if recipes else 0.0,
        "notes": "Fallback lokal; set ATRIA_API_KEY untuk rekomendasi AI yang lebih variatif.",
    }


def _recipe(name: str, items: list[str]) -> dict:
    """Sum the listed database foods into one recipe card."""
    by_name = {f["name"].lower(): f for f in FOODS}
    found = [by_name[i.lower()] for i in items if i.lower() in by_name]
    return {
        "name": name,
        "kcal": round(sum(f["kcal"] for f in found)),
        "protein_g": round(sum(f["protein_g"] for f in found), 1),
        "carb_g": round(sum(f["carb_g"] for f in found), 1),
        "fat_g": round(sum(f["fat_g"] for f in found), 1),
        "ingredients": [f["name"] for f in found],
        "steps": [
            "Potong dan cuci bahan.",
            "Tumis bumbu, masukkan protein.",
            "Tambahkan sayuran, masak 5 menit.",
            "Sesuaikan garam, sajikan.",
        ],
        "prep_min": 20,
        "volume_eating": True,
        "tags": ["tinggi protein", "cepat", "lokal"],
    }
