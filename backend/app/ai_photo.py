"""Feature #7: photo -> nutrition estimates.

The model names dishes and estimates portions; the local Indonesian
database supplies the nutrition values whenever a dish is in it. That
keeps the numbers consistent with everything else in the app (and with
the user's DB-matched text logs) instead of letting the vision model
invent its own per-dish calorie counts.

Images are downsampled before upload because Gemini's per-minute token
budget is tight, and it cannot read plate detail much beyond ~800px.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re

from .atria_client import extract_json, num
from .config import get_settings
from .foods import search_foods
from .gemini_client import vision_chat

log = logging.getLogger("defisitku.photo")
settings = get_settings()

VISION_SYSTEM = """Kamu adalah asisten nutrisi untuk aplikasi Indonesia bernama Nurtra.
Tugas: identifikasi makanan/minuman dalam foto DAN estimasi porsinya.

Aturan ketat:
- Jawab HANYA dengan JSON valid, tanpa teks penjelasan apa pun.
- Tulis nama makanan dalam bahasa Indonesia sehari-hari (contoh: "Nasi Putih", "Dada Ayam Bakar", "Sayur Bening").
- Estimasi gram per porsi seakurat mungkin dari volume yang terlihat.
- WAJIB isi kcal, protein_g, carb_g, fat_g untuk setiap makanan, dalam jumlah total untuk porsi yang terlihat.
- Kalau tidak yakin sebuah item adalah makanan, lewati.
- Jika foto bukan makanan, balas {"foods": [], "message": "Foto ini tidak terlihat seperti makanan."}.
"""

VISION_SCHEMA = """{
  "foods": [
    {
      "name": "nama makanan bahasa Indonesia",
      "est_grams": "estimasi gram porsi ini, angka",
      "kcal": "estimasi total kalori untuk porsi ini",
      "protein_g": "gram protein untuk porsi ini",
      "carb_g": "gram karbohidrat untuk porsi ini",
      "fat_g": "gram lemak untuk porsi ini",
      "confidence": "0-1"
    }
  ],
  "message": "catatan singkat atau null"
}"""

# Long edge cap before upload. Gemini reasons per image token, so a 4K
# phone photo costs the whole minute quota for detail it cannot use.
MAX_PX = 768
JPEG_QUALITY = 82


def _downsample(image_bytes: bytes, mime_type: str) -> tuple[str, str, str | None]:
    """Shrink to MAX_PX long edge, re-encode JPEG, return (b64, mime, error).

    Falls back to the original bytes if PIL is unavailable or the decode
    fails, so the feature still works on a minimal install.
    """
    try:
        from PIL import Image
    except ImportError:
        return base64.b64encode(image_bytes).decode(), mime_type, None

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.draft("RGB", (MAX_PX * 2, MAX_PX * 2))
        img = img.convert("RGB")
        w, h = img.size
        scale = MAX_PX / max(w, h)
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return base64.b64encode(buf.getvalue()).decode(), "image/jpeg", None
    except Exception as exc:
        log.warning("downsample failed, using original: %s", exc)
        return base64.b64encode(image_bytes).decode(), mime_type, None


def _local_lookup(name: str, grams: float) -> dict | None:
    """Best DB match for a dish name; scales per-100 g to `grams`."""
    hits = search_foods(name, limit=1)
    if not hits:
        return None
    f = hits[0]
    # Restaurant entries already carry a realistic per-portion gram weight,
    # so trust that reference portion over the model's volume guess.
    scale = grams / max(1.0, f.get("portion_g") or 100)
    return {
        "name": f["name"],
        "kcal": round(f["kcal"] * scale, 1),
        "protein_g": round(f["protein_g"] * scale, 1),
        "carb_g": round(f["carb_g"] * scale, 1),
        "fat_g": round(f["fat_g"] * scale, 1),
        "portion_g": round(grams),
        "servings": round(scale, 2),
        "volume_eating": f["volume_eating"],
        "source": "local-db",
        "match": f["name"],
        "confidence": round(min(1.0, scale and 0.8), 2),
    }


def _local_fallback(prompt_text: str) -> dict:
    """No Gemini key / Gemini down: parse the filename-derived hint instead.

    Keeps the endpoint from dead-ending. Called after the model has already
    tried, so the hint is whatever the caller knew about the photo.
    """
    hits = search_foods(prompt_text or "", limit=3)
    return {
        "foods": [],
        "candidates": [
            {
                "name": h["name"],
                "kcal": h["kcal"],
                "protein_g": h["protein_g"],
                "carb_g": h["carb_g"],
                "fat_g": h["fat_g"],
                "portion_g": h["portion_g"],
                "servings": 1.0,
                "volume_eating": h["volume_eating"],
                "source": "local-db",
                "confidence": 0.5,
                "needs_portion": True,
            }
            for h in hits
        ],
        "source": "local-fallback",
        "message": (
            "AI foto tidak tersedia sekarang. Pilih dari kandidat di bawah dan "
            "atur porsinya sendiri."
        ),
    }


def recognise_food(
    image_bytes: bytes, mime_type: str, hint: str = ""
) -> dict:
    """Photo -> recognised foods with nutrition values.

    Returns either {"foods": [...]} (ready to add) or
    {"candidates": [...]} (user must pick + set a portion) when the model
    is unavailable or unsure. Never raises.
    """
    if not image_bytes:
        return {"foods": [], "source": "empty", "message": "Gambar kosong."}

    if not settings.gemini_ready:
        return _local_fallback(hint)

    b64, mime, err = _downsample(image_bytes, mime_type)

    payload = {
        "tugas": "Identifikasi makanan dalam foto ini dan estimasi gramnya.",
        "output_schema": VISION_SCHEMA,
        "hint": hint or None,
    }
    content = vision_chat(
        prompt=VISION_SYSTEM + "\n\n" + json.dumps(payload, ensure_ascii=False),
        image_b64=b64,
        mime_type=mime,
        temperature=0.2,
        max_tokens=900,
        timeout=120.0,
    )

    parsed = extract_json(content)
    if not parsed or not isinstance(parsed, dict):
        log.warning("no usable JSON from Gemini vision")
        return _local_fallback(hint)

    raw_foods = parsed.get("foods") or []
    if not raw_foods:
        # Model either saw no food or declined; surface its own explanation.
        return {
            "foods": [],
            "source": "gemini",
            "message": str(parsed.get("message") or "")
            or "Tidak ada makanan terdeteksi di foto ini.",
        }

    out: list[dict] = []
    for rf in raw_foods:
        if not isinstance(rf, dict):
            continue
        name = str(rf.get("name") or "").strip()
        if not name:
            continue
        grams = num(rf.get("est_grams")) or 0.0
        # Enforce a sane floor so a dish is never reported as ~0 g.
        grams = max(grams, 30.0)

        local = _local_lookup(name, grams)
        if local:
            local["ai_name"] = name
            local["ai_confidence"] = round(min(1.0, num(rf.get("confidence"))), 2)
            out.append(local)
            continue

        # Not in the DB: carry the model's estimate straight through. This is
        # the only path where nutrition numbers come from the model, and the
        # frontend marks these so the user can sanity-check them.
        # `or` chain with a reasonable default so an absent field never
        # yields a nutrition-free entry.
        kcal = num(rf.get("kcal")) or 0.0
        prot = num(rf.get("protein_g")) or 0.0
        carb = num(rf.get("carb_g")) or 0.0
        fat = num(rf.get("fat_g")) or 0.0
        if not kcal and not prot and not carb and not fat:
            # The model returned a name with no nutrition data. Give the
            # frontend something to edit rather than a zero-calorie row.
            log.info("gemini gave no nutrition for %r", name)
            out.append(
                {
                    "name": name[:80],
                    "kcal": 0.0,
                    "protein_g": 0.0,
                    "carb_g": 0.0,
                    "fat_g": 0.0,
                    "portion_g": round(grams),
                    "servings": 1.0,
                    "volume_eating": False,
                    "source": "gemini-needs-edit",
                    "confidence": round(min(1.0, num(rf.get("confidence"))), 2),
                    "needs_portion": True,
                    "message": (
                        "Estimasi nutrisi tidak tersedia untuk item ini. "
                        "Isi kalori manual di langkah berikutnya."
                    ),
                }
            )
            continue

        out.append(
            {
                "name": name[:80],
                "kcal": round(kcal, 1),
                "protein_g": round(prot, 1),
                "carb_g": round(carb, 1),
                "fat_g": round(fat, 1),
                "portion_g": round(grams),
                "servings": 1.0,
                "volume_eating": False,
                "source": "gemini",
                "confidence": round(min(1.0, num(rf.get("confidence"))), 2),
                "needs_portion": True,
            }
        )

    if not out:
        return _local_fallback(hint)

    return {
        "foods": out,
        "source": "gemini",
        "model": settings.gemini_model,
        "message": str(parsed.get("message") or "") or None,
    }
