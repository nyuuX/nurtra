"""Feature #6: weekly report insights and recommendations."""

from __future__ import annotations

import json
import logging

from .atria_client import chat, extract_json, num
from .config import get_settings

log = logging.getLogger("defisitku.insights")
settings = get_settings()

INSIGHT_SYSTEM = """Kamu adalah coach nutrisi untuk Nurtra, aplikasi defisit kalori.
Input: JSON ringkasan mingguan (text-only). Output: HANYA JSON valid, tanpa penjelasan.
Tugas: (1) analisis tren asupan vs target, (2) deteksi plateau bila berat badan stagnan >= 3 minggu, (3) rekomendasi konkret untuk minggu depan.
Bahasa Indonesia. Ringkas dan to the point."""

INSIGHT_SCHEMA = {
    "summary": "1-2 kalimat ringkasan minggu",
    "mood": "salah satu: on_track | plateau | over_target | under_eating | insufficient_data",
    "insights": [
        {
            "type": "protein | calories | plateau | fasting | exercise | hydration",
            "title": "string",
            "detail": "string",
            "severity": "info | warning | alert",
        }
    ],
    "recommendations": [
        {
            "category": "nutrition | training | behavior",
            "action": "tindakan konkret untuk minggu depan",
            "rationale": "kenapa ini relevan dengan datanya",
        }
    ],
    "next_week_target_kcal": "number atau null",
    "next_week_protein_g": "number atau null",
    "confidence": "number 0-1",
}


def _slim_week(week: dict) -> dict:
    """Trim the payload to what the model actually reasons about.

    Atria Dawn is a reasoning model: every extra token costs latency, and
    the per-day item lists do not change the analysis.
    """
    # The report endpoint nests these under range/stats; read both shapes so
    # the model sees real numbers either way.
    rng = week.get("range") or {}
    stats = week.get("stats") or {}
    return {
        "start_date": rng.get("start") or week.get("start_date"),
        "end_date": rng.get("end") or week.get("end_date"),
        "target_kcal": week.get("target_kcal"),
        "avg_kcal": stats.get("avg_kcal", week.get("avg_kcal")),
        "avg_protein_g": stats.get("avg_protein_g", week.get("avg_protein_g")),
        "protein_target_g": stats.get("protein_target_g", week.get("protein_target_g")),
        "adherence": stats.get("adherence", week.get("adherence")),
        "plateau": week.get("plateau"),
        "weight_trend": week.get("weight_trend"),
    }


def weekly_insights(week: dict) -> dict:
    if not settings.atria_ready:
        return _local_insights(week)

    try:
        # Atria Dawn is a reasoning model: this call can take 60-150s.
        payload = {"schema": INSIGHT_SCHEMA, "week": _slim_week(week)}
        content = chat(
            [
                {"role": "system", "content": INSIGHT_SYSTEM},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
            ],
            temperature=0.4,
            max_tokens=1200,
            timeout=240.0,
        )
        parsed = extract_json(content)
        if parsed and isinstance(parsed, dict) and parsed.get("insights") is not None:
            parsed.setdefault("recommendations", [])
            parsed["source"] = "atria"
            parsed["atria_raw"] = content
            return parsed
        log.info("weekly_insights: no usable JSON from Atria, using local fallback")
    except Exception as exc:
        log.warning("weekly_insights: Atria failed, using local fallback: %s", exc)

    return _local_insights(week)


def _local_insights(week: dict) -> dict:
    """Deterministic fallback so the report view is never empty."""
    adherence = week.get("adherence", {})
    rate = num(adherence.get("rate"))
    avg_kcal = num(week.get("avg_kcal"))
    target = num(week.get("target_kcal"))
    protein = num(week.get("avg_protein_g"))
    protein_target = num(week.get("protein_target_g"))
    plateau = bool(week.get("plateau"))
    days_logged = int(num(adherence.get("days_logged")))

    insights: list[dict] = []
    recs: list[dict] = []

    if days_logged < 3:
        insights.append(
            {
                "type": "calories",
                "title": "Data belum cukup",
                "detail": f"Baru {days_logged} hari terlog minggu ini. Log minimal 5 hari untuk insight akurat.",
                "severity": "info",
            }
        )
        return {
            "summary": "Data mingguan masih minim; fokus bangun kebiasaan log harian dulu.",
            "mood": "insufficient_data",
            "insights": insights,
            "recommendations": recs,
            "next_week_target_kcal": None,
            "next_week_protein_g": None,
            "confidence": 0.3,
            "source": "local",
        }

    # ---- Calorie axis ------------------------------------------------
    if avg_kcal > target * 1.10:
        insights.append(
            {
                "type": "calories",
                "title": "Asupan di atas target",
                "detail": f"Rata-rata {avg_kcal:.0f} kkal vs target {target:.0f} kkal "
                f"(+{avg_kcal - target:.0f} kkal/hari).",
                "severity": "warning",
            }
        )
        recs.append(
            {
                "category": "nutrition",
                "action": "Makan sayuran dan jamur (volume eating) sebelum makan utama untuk membatasi kalori tanpa lapar.",
                "rationale": f"Defisit terhapus sekitar {(avg_kcal - target) * 7:.0f} kkal/minggu.",
            }
        )
    elif avg_kcal < target * 0.80:
        insights.append(
            {
                "type": "calories",
                "title": "Asupan terlalu rendah",
                "detail": f"Rata-rata {avg_kcal:.0f} kkal, hanya {avg_kcal / max(target, 1) * 100:.0f}% "
                "dari target. Risiko kehilangan massa otot dan rebound.",
                "severity": "alert",
            }
        )
        recs.append(
            {
                "category": "nutrition",
                "action": "Tambah 1 camilan protein (telur rebus, edamame, whey) untuk menambal asupan harian.",
                "rationale": "Defisit terlalu agresif menyebabkan adaptasi metabolik dan rebound.",
            }
        )
    else:
        insights.append(
            {
                "type": "calories",
                "title": "Asupan dalam koridor target",
                "detail": f"Rata-rata {avg_kcal:.0f} kkal vs target {target:.0f} kkal. Pertahankan!.",
                "severity": "info",
            }
        )

    # ---- Protein axis ------------------------------------------------
    if protein < protein_target * 0.85:
        insights.append(
            {
                "type": "protein",
                "title": "Protein kurang",
                "detail": f"Rata-rata {protein:.0f} g vs target {protein_target:.0f} g "
                f"({protein / max(protein_target, 1) * 100:.0f}%).",
                "severity": "warning",
            }
        )
        recs.append(
            {
                "category": "nutrition",
                "action": f"Tambah ~{protein_target - protein:.0f} g protein/hari dari dada ayam, tempe, tahu, telur, atau ikan.",
                "rationale": "Protein cukup menjaga massa otot saat defisit dan meningkatkan rasa kenyang.",
            }
        )

    # ---- Plateau axis ------------------------------------------------
    if plateau:
        insights.append(
            {
                "type": "plateau",
                "title": "Deteksi stagnasi berat badan",
                "detail": "Berat badan rata-rata stagnan >= 3 minggu. Ini normal, bukan kegagalan.",
                "severity": "warning",
            }
        )
        recs.append(
            {
                "category": "behavior",
                "action": "Ambil refeed day 1x/minggu pada hari latihan berat, atau tambah 8-10k langkah/hari.",
                "rationale": "Plateau bisa karena retensi air, bukan berhentinya fat-loss; naikkan NEAT daripada memperdalam defisit.",
            }
        )
        recs.append(
            {
                "category": "training",
                "action": "Tambah 1 sesi angkat beban atau 2x20 menit jalan cepat untuk menambah pengeluaran tanpa menambah lapar.",
                "rationale": "NEAT dan sesi resistance paling efektif memecahkan plateau tanpa memperdalam defisit.",
            }
        )

    if not recs:
        recs.append(
            {
                "category": "behavior",
                "action": "Pertahankan pola minggu ini; catat berat badan 2-3x/minggu untuk memantau tren.",
                "rationale": "Konsistensi saat ini sudah memenuhi target protein dan kalori.",
            }
        )

    mood = "on_track"
    if plateau:
        mood = "plateau"
    elif avg_kcal > target * 1.10:
        mood = "over_target"
    elif avg_kcal < target * 0.80:
        mood = "under_eating"

    next_kcal = None
    if avg_kcal > target * 1.10:
        next_kcal = round(target - (avg_kcal - target) * 0.5)
    elif avg_kcal < target * 0.80:
        next_kcal = round(target + (target - avg_kcal) * 0.5)

    return {
        "summary": (
            f"Kepatuhan {rate:.0f}%, asupan rata-rata {avg_kcal:.0f} kkal "
            f"(target {target:.0f}), protein {protein:.0f} g."
        ),
        "mood": mood,
        "insights": insights,
        "recommendations": recs,
        "next_week_target_kcal": next_kcal,
        "next_week_protein_g": None,
        "confidence": 0.6,
        "source": "local",
    }
