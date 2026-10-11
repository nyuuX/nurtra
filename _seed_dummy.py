"""Seed 7 days of realistic dummy data for banyusamuderapt@gmail.com.

Profile: male, 21, 60 kg, 170 cm, light activity, 0.5 kg/week target.
        -> TDEE 2148, target 1611 kcal, protein 108 g.

Story the data tells (so the report features are actually exercisable):
  - Intake mostly at/below target with two over days -> adherence ~70-85%,
    so the bar chart shows a mix of green bars and over-target bars.
  - Weight trends DOWN across the week (60.9 -> 59.6) with daily water
    noise, so the smooth spline + least-squares trend has a negative slope
    to report and detect_plateau stays False.
  - Protein averages near target so avg protein stat is meaningful.
  - Two exercise days so the warm overlay bars appear.
  - One unlogged day so the placeholder bar renders.

Idempotent: days matching these dates are REPLACED, so re-running won't
stack duplicates. Existing days outside the window are left alone.

Run:  .venv/Scripts/python.exe _seed_dummy.py
"""

from __future__ import annotations

import json
import secrets
import sys
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "defisitku.json"
EMAIL = "banyusamuderapt@gmail.com"
TARGET = 1611


def entry(name, meal, kcal, protein_g, carb_g, fat_g, portion_g, servings=1.0):
    """One meal entry in the same shape addMeal writes."""
    # volume_eating matches the backend rule: low kcal/100g + high fiber/water
    vol = (kcal / max(1, portion_g) * 100) < 150 and name in {
        "Pepaya", "Semangka", "Paprika Merah", "Salad Sayur", "Sup Bening Bayam",
    }
    return {
        "id": secrets.token_hex(4),
        "name": name,
        "meal": meal,
        "kcal": round(kcal, 1),
        "protein_g": round(protein_g, 1),
        "carb_g": round(carb_g, 1),
        "fat_g": round(fat_g, 1),
        "portion_g": portion_g,
        "servings": servings,
        "volume_eating": vol,
        "time": "12:00",
    }


def exercise(name, kcal, mins, time):
    return {
        "id": secrets.token_hex(4),
        "name": name,
        "kcal": kcal,
        "duration_min": mins,
        "time": time,
    }


def build_day(d: date, weight: float, meals: list, exercises: list) -> dict:
    return {
        "date": d.isoformat(),
        "meals": meals,
        "exercises": exercises,
        "weight_kg": weight,
    }


def main() -> int:
    if not DB_PATH.exists():
        print("DB not found:", DB_PATH)
        return 1

    data = json.loads(DB_PATH.read_text(encoding="utf-8"))
    user = data.get("users", {}).get(EMAIL)
    if not user:
        print("user not found:", EMAIL)
        return 1

    today = date.today()
    # Walk back to the most recent Monday, so the seeded block aligns to the
    # report's Mon-Sun week rather than floating mid-week.
    start = today - timedelta(days=today.weekday())
    dates = [start + timedelta(days=i) for i in range(7)]
    iso_dates = {d.isoformat() for d in dates}

    # (date_offset, weight, meals, exercises)
    # Intake hovers around the 1611 target: two over days, one unlogged.
    days = [
        # Mon: near target, clean day
        build_day(
            dates[0], 60.9,
            [
                entry("Telur Dadar 2 Butir", "breakfast", 295, 20.8, 3.2, 22.4, 160),
                entry("Nasi Putih", "lunch", 360, 7.5, 81.0, 1.8, 300),
                entry("Dada Ayam Tanpa Kulit", "lunch", 248, 46.5, 0.0, 5.4, 150),
                entry("Tahu Kukus", "dinner", 180, 14.4, 7.2, 10.8, 150),
                entry("Sup Bening Bayam", "dinner", 70, 2.0, 11.0, 1.5, 200),
                entry("Pepaya", "snack", 110, 1.2, 27.6, 0.4, 300),
                entry("Susu UHT Plain", "snack", 180, 9.0, 18.0, 7.5, 300),
            ],
            [exercise("Jalan Cepat", 110, 30, "07:15")],
        ),
        # Tue: well over target (cheat day) — gives the chart an over bar
        build_day(
            dates[1], 61.2,
            [
                entry("Nasi Merah", "breakfast", 375, 8.8, 80.8, 3.2, 320),
                entry("Tempe Bakar", "lunch", 290, 27.0, 13.5, 16.5, 150),
                entry("Nasi Putih", "lunch", 360, 7.5, 81.0, 1.8, 300),
                entry("Ayam Bakar", "lunch", 403, 48.0, 12.0, 19.5, 200),
                entry("Mie Goreng", "dinner", 570, 16.5, 78.0, 22.5, 300),
                entry("Es Teh Manis", "snack", 135, 0.0, 34.0, 0.0, 250),
            ],
            [],
        ),
        # Wed: slightly under target
        build_day(
            dates[2], 60.7,
            [
                entry("Nasi Putih", "breakfast", 300, 6.2, 67.5, 1.5, 250),
                entry("Telur Rebus 2 Butir", "breakfast", 206, 16.8, 1.6, 14.7, 160),
                entry("Daging Sapi", "lunch", 500, 52.0, 0.0, 34.0, 200),
                entry("Sayur Bening", "dinner", 130, 4.0, 20.0, 3.0, 400),
                entry("Semangka", "snack", 122, 2.4, 30.7, 0.5, 400),
            ],
            [],
        ),
        # Thu: under target with a workout
        build_day(
            dates[3], 60.4,
            [
                entry("Bubur Ayam", "breakfast", 420, 27.9, 56.0, 12.0, 500),
                entry("Nasi Putih", "lunch", 300, 6.2, 67.5, 1.5, 250),
                entry("Ikan Kukus", "dinner", 293, 43.4, 0.0, 10.6, 200),
                entry("Paprika Merah", "snack", 62, 2.0, 14.4, 0.6, 200),
                entry("Susu UHT Coklat", "snack", 173, 10.5, 25.5, 5.2, 300),
            ],
            [exercise("Sepeda", 165, 45, "17:30")],
        ),
        # Fri: slightly over target
        build_day(
            dates[4], 60.0,
            [
                entry("Oatmeal + Pisang", "breakfast", 453, 14.8, 78.9, 9.9, 415),
                entry("Nasi Putih", "lunch", 300, 6.2, 67.5, 1.5, 250),
                entry("Dada Ayam Tanpa Kulit", "lunch", 330, 62.0, 0.0, 7.2, 200),
                entry("Kangkung Tumis", "dinner", 248, 9.0, 20.3, 18.0, 340),
                entry("Es Teh Manis", "snack", 135, 0.0, 34.0, 0.0, 250),
            ],
            [],
        ),
        # Sat: unlogged -> placeholder bar, no weight
        build_day(dates[5], None, [], []),
        # Sun: near target, big workout, week ends lighter
        build_day(
            dates[6], 59.6,
            [
                entry("Oatmeal + Pisang", "breakfast", 453, 14.8, 78.9, 9.9, 415),
                entry("Nasi Putih", "lunch", 300, 6.2, 67.5, 1.5, 250),
                entry("Dada Ayam Tanpa Kulit", "lunch", 330, 62.0, 0.0, 7.2, 200),
                entry("Salad Sayur", "dinner", 203, 6.8, 27.0, 9.0, 405),
                entry("Yogurt Plain", "snack", 267, 26.7, 32.0, 5.3, 400),
            ],
            [exercise("Lari", 220, 35, "06:30")],
        ),
    ]

    # Idempotent replace
    kept = [d for d in user.get("days", []) if d.get("date") not in iso_dates]
    user["days"] = kept + days
    user["recent_searches"] = ["nasi putih", "dada ayam", "tempe", "telur"]

    # Seed one favorite so the favorites chip row has content
    favs = user.setdefault("favorites", [])
    if not any(f.get("name") == "Chicken Rice Bowl" for f in favs):
        favs.append(
            {
                "id": secrets.token_hex(4),
                "name": "Chicken Rice Bowl",
                "kcal": 430.0,
                "protein_g": 41.0,
                "carb_g": 48.0,
                "fat_g": 12.0,
                "ingredients": ["Dada Ayam Tanpa Kulit", "Nasi Merah", "Sawi Hijau"],
            }
        )

    DB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Report what we wrote so the numbers can be eyeballed
    print(f"Seeded {len(days)} days for {EMAIL} ({dates[0]} .. {dates[-1]})")
    for d in days:
        kcal = sum(m["kcal"] for m in d["meals"])
        protein = sum(m["protein_g"] for m in d["meals"])
        ex = sum(e["kcal"] for e in d["exercises"])
        w = d["weight_kg"]
        tag = " (unlogged)" if not d["meals"] else ""
        print(
            f"  {d['date']}  {kcal:5.0f} kkal | P {protein:5.1f} g | ex {ex:3.0f} | "
            f"w {str(w):>4} kg{tag}"
        )
    print(f"\nTarget {TARGET} kcal/day · protein 108 g")
    logged = [d for d in days if d["meals"]]
    avg = sum(sum(m["kcal"] for m in d["meals"]) for d in logged) / len(logged)
    print(f"Logged-day avg intake: {avg:.0f} kcal")
    return 0


if __name__ == "__main__":
    sys.exit(main())
