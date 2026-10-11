"""Feature #2: free-text food log parsing.

Strategy: match the local Indonesian database first (instant, free), then
ask Gemini to estimate whatever is left (restaurant dishes, odd
portions). If Gemini is unavailable, the DB result stands on its own.
"""

from __future__ import annotations

import json
import logging
import re

from .atria_client import extract_json, num
from .gemini_client import text_chat
from .config import get_settings
from .foods import search_foods

log = logging.getLogger("defisitku.parse")
settings = get_settings()

PARSE_SYSTEM = """Kamu adalah asisten nutrisi untuk aplikasi Indonesia bernama Nurtra.
Tugas: ubah deskripsi makanan dalam bahasa Indonesia menjadi data nutrisi terstruktur.

Aturan:
- Estimasi kalori dan makro per porsi yang disebutkan (default 1 porsi = 100 g makanan matang kecuali dinyatakan lain).
- Nasi: 1 porsi = 200 g, kecuali "1 mangkuk kecil" = 150 g.
- Telur: 1 butir = 60 g.
- volume_eating = true hanya jika makanan rendah kalori (<150 kkal/100 g) DAN tinggi serat/air (sayur, buah, jamur).
- Output HANYA JSON valid, tanpa penjelasan apapun."""

PARSE_SCHEMA = {
    "foods": [
        {
            "name": "nama makanan",
            "kcal": "total kalori untuk porsi ini",
            "protein_g": "gram protein",
            "carb_g": "gram karbohidrat",
            "fat_g": "gram lemak",
            "portion_g": "gram porsi ini",
            "servings": "faktor porsi, default 1.0",
            "volume_eating": "boolean",
        }
    ],
    "confidence": "number 0-1",
    "notes": "catatan singkat atau null",
}


def parse_foods(text: str) -> dict:
    """Free-text meal description -> structured foods list."""
    if not text or not text.strip():
        return {"foods": [], "source": "empty", "confidence": 0.0, "notes": "Input kosong."}

    local = _local_parse(text)

    if settings.gemini_ready:
        try:
            payload = {
                "text": text,
                "instruction": (
                    "Isi JSON sesuai schema. Untuk makanan yang sudah ada di "
                    "local_matches, pakai angka itu dan set source='local'. "
                    "Estimasi sisanya dan set source='gemini'."
                ),
                "schema": PARSE_SCHEMA,
                "local_matches": local["foods"] or None,
            }
            content = text_chat(
                [
                    {"role": "system", "content": PARSE_SYSTEM},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                temperature=0.2,
            )
            parsed = extract_json(content)
            if parsed and isinstance(parsed, dict) and parsed.get("foods") is not None:
                # Filter out invalid non-food items returned with zero kcal/confidence 0
                valid_foods = [
                    f for f in parsed.get("foods", [])
                    if isinstance(f, dict) and (num(f.get("kcal")) > 0 or num(f.get("protein_g")) > 0 or num(f.get("carb_g")) > 0 or num(f.get("fat_g")) > 0)
                ]
                if valid_foods or local["foods"]:
                    parsed["foods"] = valid_foods or local["foods"]
                    parsed["source"] = "gemini"
                    parsed["gemini_raw"] = content
                    return _normalise_parse(parsed, text)
            log.info("parse_foods: no usable JSON from Atria, using local matches")
        except Exception as exc:
            log.warning("parse_foods: Atria failed, using local fallback: %s", exc)

    if local["foods"]:
        local["source"] = "local-db"
        return local

    return {
        "foods": [],
        "source": "unparsed",
        "confidence": 0.0,
        "notes": "Tidak dapat mengenali makanan. Coba Pencarian atau Quick Add manual.",
    }


def _local_parse(text: str) -> dict:
    """Split on commas / 'dan' / '+', match each part against the local DB.

    The DB stores per-100 g values, so scale by the servings implied by the
    quantity words in the phrase (default 1 x 100 g, or the food's own
    reference portion for things like telur/roti).
    """
    parts = re.split(r"[,+]| dan ", text.lower())
    foods: list[dict] = []
    confidences: list[float] = []

    for part in parts:
        part = part.strip()
        if not part:
            continue
        qty_match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)?\s*(x|buah|butir|porsi|mangkuk|piring|gram|gr|g)?\b", part)
        count = 1.0
        unit = ""
        if qty_match:
            count = float(qty_match.group(1) or 1)
            unit = (qty_match.group(2) or "").lower()
            if unit in ("gram", "gr", "g"):
                count /= 100.0  # per-100 g basis

        query = re.sub(r"^[0-9\s]*(x|buah|butir|porsi|mangkuk|piring|gram|gr|g)?\s*", "", part)
        hits = search_foods(query, limit=1)
        if not hits:
            continue
        f = dict(hits[0])

        # Every unit resolves to "count x the food's reference portion"
        # (gram/gr/g were already normalised to a 100 g multiple above).
        scale = count
        foods.append(
            {
                "name": f["name"],
                "kcal": round(f["kcal"] * scale),
                "protein_g": round(f["protein_g"] * scale, 1),
                "carb_g": round(f["carb_g"] * scale, 1),
                "fat_g": round(f["fat_g"] * scale, 1),
                "portion_g": round(f["portion_g"] * scale),
                "servings": scale,
                "volume_eating": f["volume_eating"],
                "source": "local",
            }
        )
        confidences.append(0.75)

    return {
        "foods": foods,
        "confidence": round(sum(confidences) / len(confidences), 2) if confidences else 0.0,
        "notes": None,
    }


def _normalise_parse(parsed: dict, original: str) -> dict:
    """Coerce Atria output to the exact shape the frontend expects."""
    foods = []
    for f in parsed.get("foods", []):
        if not isinstance(f, dict):
            continue
        foods.append(
            {
                "name": str(f.get("name") or original)[:80],
                "kcal": round(num(f.get("kcal"))),
                "protein_g": round(num(f.get("protein_g")), 1),
                "carb_g": round(num(f.get("carb_g")), 1),
                "fat_g": round(num(f.get("fat_g")), 1),
                "portion_g": int(num(f.get("portion_g")) or 100),
                "servings": num(f.get("servings")) or 1.0,
                "volume_eating": bool(f.get("volume_eating")),
                "source": "gemini",
            }
        )
    parsed["foods"] = foods
    return parsed
