"""TDEE/BMR calculator, macro targets, and fasting-window helpers.

Formulas: Mifflin-St Jeor for BMR (most accurate for the general
population without body-fat data), Katch-McArdle when the user supplies
body fat %, plus standard activity multipliers and a sane deficit cap.

All units: kg / cm / kcal.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from .config import local_now

# ----------------------------- Constants -----------------------------

ACTIVITY_LEVELS: dict[str, float] = {
    "sedentary": 1.20,       # little or no exercise, desk job
    "light": 1.375,          # light exercise 1-3 days/week
    "moderate": 1.550,       # moderate exercise 3-5 days/week
    "active": 1.725,         # hard exercise 6-7 days/week
    "very_active": 1.90,     # very hard exercise + physical job
}

Gender = Literal["male", "female"]

# 1 kg body fat ~= 7700 kcal
KCAL_PER_KG_FAT = 7700.0

# Dietbreakers / safety rails
MIN_SAFE_KCAL = 1200.0        # floor for women (conservative)
MIN_SAFE_KCAL_MALE = 1500.0   # floor for men
MAX_DEFICIT_PCT = 0.25        # never cut more than 25% of TDEE
MAX_WEEKLY_LOSS_KG = 1.0      # >1 kg/week is mostly water + muscle

# Indonesian-style default macro split (protein prioritised for muscle
# retention in a deficit). Values are fractions of total kcal.
DEFAULT_MACRO_SPLIT: dict[str, float] = {
    "protein": 0.30,   # 30% — highest priority (feature #4)
    "carb": 0.40,      # 40% — fuel for training
    "fat": 0.30,       # 30% — hormonal health
}
KCAL_PER_GRAM = {"protein": 4.0, "carb": 4.0, "fat": 9.0}

# Fasting protocols (feature #3) — hours fasted : hours eating
FASTING_PROTOCOLS: dict[str, tuple[int, int]] = {
    "12:12": (12, 12),
    "14:10": (14, 10),
    "16:8": (16, 8),
    "18:6": (18, 6),
    "20:4": (20, 4),
}


# --------------------------- BMR / TDEE ------------------------------

def calc_bmr(
    gender: Gender,
    weight_kg: float,
    height_cm: float,
    age: int,
    body_fat_pct: float | None = None,
) -> float:
    """Basal Metabolic Rate.

    Uses Katch-McArdle when body fat is known (most accurate), otherwise
    Mifflin-St Jeor.
    """
    if body_fat_pct is not None and 3.0 <= body_fat_pct <= 60.0:
        lbm = weight_kg * (1.0 - body_fat_pct / 100.0)
        return 370.0 + (21.6 * lbm)

    base = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age)
    return base + (5.0 if gender == "male" else -161.0)


def calc_tdee(
    gender: Gender,
    weight_kg: float,
    height_cm: float,
    age: int,
    activity: str,
    body_fat_pct: float | None = None,
) -> float:
    """Total Daily Energy Expenditure = BMR x activity multiplier."""
    multiplier = ACTIVITY_LEVELS.get(activity, ACTIVITY_LEVELS["moderate"])
    return calc_bmr(gender, weight_kg, height_cm, age, body_fat_pct) * multiplier


def calc_target_kcal(
    tdee: float,
    weekly_loss_kg: float,
    gender: Gender,
) -> tuple[float, dict[str, float]]:
    """Daily target with safety caps applied.

    Returns (target_kcal, applied_limits) where applied_limits documents
    any rail that fired, so the UI can explain *why* the number changed.
    """
    applied: dict[str, float] = {}
    loss = max(0.0, min(weekly_loss_kg, MAX_WEEKLY_LOSS_KG))
    if loss < weekly_loss_kg:
        applied["capped_weekly_loss_kg"] = MAX_WEEKLY_LOSS_KG

    daily_deficit = (loss * KCAL_PER_KG_FAT) / 7.0
    max_deficit = tdee * MAX_DEFICIT_PCT
    if daily_deficit > max_deficit:
        daily_deficit = max_deficit
        applied["capped_deficit_kcal"] = max_deficit

    target = tdee - daily_deficit

    floor = MIN_SAFE_KCAL_MALE if gender == "male" else MIN_SAFE_KCAL
    if target < floor:
        target = floor
        applied["floored_at_kcal"] = floor

    return round(target), applied


def calc_macros(target_kcal: float, weight_kg: float) -> dict[str, dict[str, float]]:
    """Macro targets in grams from the daily kcal target.

    Protein is expressed per kg of bodyweight (the number that actually
    matters for muscle retention) and drives the ring/bar totals.
    """
    protein_g = max(100.0, round(weight_kg * 1.8))  # 1.8 g/kg floor 100 g
    protein_kcal = protein_g * KCAL_PER_GRAM["protein"]

    remaining = max(0.0, target_kcal - protein_kcal)
    fat_kcal = remaining * (DEFAULT_MACRO_SPLIT["fat"] / (
        DEFAULT_MACRO_SPLIT["carb"] + DEFAULT_MACRO_SPLIT["fat"]
    ))
    carb_kcal = remaining - fat_kcal

    return {
        "protein": {
            "gram": protein_g,
            "kcal": round(protein_kcal),
            "target_g": protein_g,
            "pct_of_kcal": round(protein_kcal / target_kcal * 100, 1) if target_kcal else 0.0,
        },
        "carb": {
            "gram": round(carb_kcal / KCAL_PER_GRAM["carb"], 1),
            "kcal": round(carb_kcal),
            "target_g": round(carb_kcal / KCAL_PER_GRAM["carb"], 1),
            "pct_of_kcal": round(carb_kcal / target_kcal * 100, 1) if target_kcal else 0.0,
        },
        "fat": {
            "gram": round(fat_kcal / KCAL_PER_GRAM["fat"], 1),
            "kcal": round(fat_kcal),
            "target_g": round(fat_kcal / KCAL_PER_GRAM["fat"], 1),
            "pct_of_kcal": round(fat_kcal / target_kcal * 100, 1) if target_kcal else 0.0,
        },
    }


# --------------------------- Fasting ---------------------------------

def parse_fasting_window(protocol: str) -> tuple[int, int] | None:
    """'16:8' -> (16, 8). Returns None for unknown protocols."""
    return FASTING_PROTOCOLS.get(protocol)


def fasting_status_for(protocol: str, now: datetime | None = None) -> dict:
    """Whether the user is currently inside their eating window.

    Assumes the eating window starts at 12:00 by convention (a common
    default for 16:8) and is closed on both ends.
    """
    proto = parse_fasting_window(protocol)
    if proto is None:
        return {"enabled": False, "protocol": protocol}
    fast_h, eat_h = proto

    now = now or local_now()  # local wall-clock; fasting windows are local
    eat_start = 12  # 12:00 local reference point
    hour = now.hour
    inside = eat_start <= hour < eat_start + eat_h

    return {
        "enabled": True,
        "protocol": protocol,
        "fast_hours": fast_h,
        "eat_hours": eat_h,
        "eating_now": bool(inside),
        "window_start": f"{eat_start:02d}:00",
        "window_end": f"{(eat_start + eat_h) % 24:02d}:00",
    }


# ------------------------- Aggregations ------------------------------

def day_kcal(day: dict) -> dict[str, float]:
    """Sum one day's entries into {kcal, protein, carb, fat, exercise}."""
    meal_kcal = sum(e.get("kcal", 0) for e in day.get("meals", []))
    exercise_kcal = sum(e.get("kcal", 0) for e in day.get("exercises", []))
    return {
        "kcal": round(meal_kcal, 1),
        "exercise": round(exercise_kcal, 1),
        "net": round(meal_kcal - exercise_kcal, 1),
        "protein": round(sum(e.get("protein_g", 0) for e in day.get("meals", [])), 1),
        "carb": round(sum(e.get("carb_g", 0) for e in day.get("meals", [])), 1),
        "fat": round(sum(e.get("fat_g", 0) for e in day.get("meals", [])), 1),
    }


def adherence_for_week(
    days: list[dict],
    target_kcal: float,
    tolerance_pct: float = 0.10,
) -> dict[str, float]:
    """Adherence = share of logged days within +/-10% of target (feature #6).

    Only days with any food log count; an unlogged day is not a failure.
    Accepts either day records (with a ``meals`` list) or the bar dicts the
    report endpoint emits (with an ``intake`` field).
    """
    logged: list[float] = []
    for d in days:
        if d.get("meals"):
            logged.append(day_kcal(d)["kcal"])
        elif d.get("intake"):
            logged.append(float(d["intake"]))
    if not logged:
        return {"rate": 0.0, "days_logged": 0, "days_on_target": 0}

    lo, hi = target_kcal * (1 - tolerance_pct), target_kcal * (1 + tolerance_pct)
    on_target = sum(1 for k in logged if lo <= k <= hi)
    return {
        "rate": round(on_target / len(logged) * 100, 1),
        "days_logged": len(logged),
        "days_on_target": on_target,
    }


def weight_trend(weights: list[dict]) -> dict:
    """Linear-regression trend over (date, weight) points.

    Uses a least-squares fit instead of raw deltas so daily water-weight
    noise does not dominate the reported trend — the point of feature #6.
    """
    pts = [(i, w["weight_kg"]) for i, w in enumerate(weights) if w.get("weight_kg")]
    if len(pts) < 2:
        return {"slope_per_day": 0.0, "change_kg": 0.0, "avg": None}

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    n = len(pts)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in pts)
    den = sum((x - mean_x) ** 2 for x in xs)
    slope = num / den if den else 0.0

    return {
        "slope_per_day": round(slope, 4),
        "change_kg": round(ys[-1] - ys[0], 2),
        "avg": round(sum(ys) / n, 2),
    }


def detect_plateau(weights: list[dict], weeks: int = 3) -> bool:
    """True if weight has moved < 0.3 kg over the last `weeks` entries."""
    recent = [w["weight_kg"] for w in weights[-weeks:] if w.get("weight_kg")]
    return len(recent) >= weeks and (max(recent) - min(recent)) < 0.3


# ----------------------------- Sanity --------------------------------

def nutrition_profile(
    gender: Gender,
    age: int,
    weight_kg: float,
    height_cm: float,
    activity: str,
    weekly_loss_kg: float,
    body_fat_pct: float | None = None,
    fasting: str | None = None,
) -> dict:
    """One-call profile builder used by the /profile endpoint."""
    tdee = round(calc_tdee(gender, weight_kg, height_cm, age, activity, body_fat_pct))
    target, limits = calc_target_kcal(tdee, weekly_loss_kg, gender)
    macros = calc_macros(target, weight_kg)

    out = {
        "tdee": tdee,
        "bmr": round(calc_bmr(gender, weight_kg, height_cm, age, body_fat_pct)),
        "target_kcal": target,
        "deficit_kcal": round(tdee - target),
        "weekly_loss_kg_target": weekly_loss_kg,
        "macros": macros,
        "limits_applied": limits,
        "activity_multiplier": ACTIVITY_LEVELS.get(activity, 1.55),
    }
    if fasting:
        out["fasting"] = fasting_status_for(fasting)
    return out


# ------------------------- Hydration ----------------------------------
# Common Indonesian practice and most clinical guidance land near 30 ml/kg
# for sedentary adults, plus extra for hot climates and training days.
# Kept simple and predictable rather than precise: the point is a target the
# user can hit, not a medical recommendation.
WATER_ML_PER_KG = 30.0
WATER_HOT_CLIMATE_ML = 500.0


def water_target(profile: dict) -> int:
    """Daily water target in ml from bodyweight, floored at a sane minimum.

    30 ml/kg with a +500 ml allowance for Indonesia's climate; activity above
    sedentary adds a little more since sweating scales with training volume.
    """
    weight = max(30.0, min(float(profile.get("weight_kg") or 70), 300.0))
    ml = weight * WATER_ML_PER_KG + WATER_HOT_CLIMATE_ML

    activity = (profile.get("activity") or "sedentary").lower()
    if activity in ("light", "moderate"):
        ml += 350.0
    elif activity in ("active", "very_active", "very active"):
        ml += 700.0

    return int(round(min(ml, 6000.0)))
