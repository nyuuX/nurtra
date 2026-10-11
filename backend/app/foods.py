"""Local Indonesian food database — raw ingredients, cooked dishes, and
restaurant menus. Values are per 100 g unless `portion_g` says otherwise.

This is the offline fallback for food search (feature #2) and the
`demo`-mode answer for AI parsing. `volume_eating` flags low-kcal,
high-satiety foods (feature #4).
"""

from __future__ import annotations

# (name, aliases, kcal, protein, carb, fat, portion_g, category, volume_eating)
_RAW: tuple[tuple[str, tuple[str, ...], float, float, float, float, int, str, bool], ...] = (
    # ---- Staple carbs ------------------------------------------------
    ("Nasi Putih", ("nasi", "rice", "cooked white rice"), 175, 3.5, 38.0, 0.5, 100, "staple", False),
    ("Nasi Merah", ("nasi merah", "brown rice", "red rice"), 160, 3.0, 34.0, 1.2, 100, "staple", False),
    ("Kentang Rebus", ("kentang", "potato", "kentang rebus"), 90, 2.0, 20.0, 0.1, 100, "staple", True),
    ("Ubi Rebus", ("ubi", "sweet potato", "ubi jalar"), 110, 1.5, 25.0, 0.1, 100, "staple", True),
    ("Roti Gandum", ("roti", "whole wheat bread", "roti gandum"), 240, 9.0, 40.0, 3.5, 100, "staple", False),
    ("Mie Instant", ("mie", "indomie", "instant noodle"), 380, 8.0, 52.0, 15.0, 100, "staple", False),

    # ---- Protein: chicken / meat ------------------------------------
    ("Dada Ayam Tanpa Kulit", ("dada ayam", "chicken breast", "ayam dada"), 165, 31.0, 0.0, 3.6, 100, "protein", False),
    ("Paha Ayam", ("paha ayam", "chicken thigh"), 209, 26.0, 0.0, 11.0, 100, "protein", False),
    ("Ayam Geprek", ("geprek", "ayam geprek"), 230, 28.0, 6.0, 11.0, 100, "protein", False),
    ("Daging Sapi", ("daging sapi", "beef", "sapi"), 250, 26.0, 0.0, 17.0, 100, "protein", False),
    ("Iga Sapi", ("iga", "beef ribs"), 320, 24.0, 0.0, 26.0, 100, "protein", False),
    ("Daging Kambing", ("kambing", "goat meat", "daging kambing"), 220, 27.0, 0.0, 12.0, 100, "protein", False),

    # ---- Protein: fish / seafood ------------------------------------
    ("Ikan Kembung", ("kembung", "kembung", "indian mackerel"), 120, 20.0, 0.0, 4.0, 100, "protein", True),
    ("Ikan Nila", ("nila", "tilapia", "ikan nila"), 110, 22.0, 0.0, 2.5, 100, "protein", True),
    ("Ikan Tongkol", ("tongkol", " tongkol", "skipjack tuna"), 110, 24.0, 0.0, 2.0, 100, "protein", True),
    ("Ikan Salmon", ("salmon"), 208, 20.0, 0.0, 13.0, 100, "protein", False),
    ("Udang", ("udang", "shrimp", "udang rebus"), 85, 20.0, 0.2, 1.0, 100, "protein", True),
    ("Cumi-cumi", ("cumi", "cumi-cumi", "squid"), 92, 15.5, 3.0, 1.0, 100, "protein", True),
    ("Telur Ayam", ("telur", "telur ayam", "egg", "telur rebus"), 155, 13.0, 1.1, 11.0, 60, "protein", False),
    ("Putih Telur", ("putih telur", "egg white", "albumin"), 52, 11.0, 0.7, 0.2, 100, "protein", True),

    # ---- Protein: plant-based (local staples) -----------------------
    ("Tahu", ("tahu", "tofu", "tahu putih"), 76, 8.0, 1.9, 4.8, 100, "protein", True),
    ("Tempe", ("tempe", "tempeh"), 193, 18.0, 9.0, 11.0, 100, "protein", True),
    ("Edamame", ("edamame"), 121, 11.0, 9.0, 5.0, 100, "protein", True),
    ("Kacang Merah", ("kacang merah", "red bean", "kacang merah rebus"), 140, 9.0, 23.0, 0.5, 100, "protein", True),
    ("Kacang Hijau", ("kacang hijau", "mung bean", "kacang hijau rebus"), 130, 8.0, 22.0, 0.5, 100, "protein", True),
    ("Susu Sapi 0% Fat", ("susu 0", "susu skim", "skim milk", "susu sapi"), 34, 3.4, 5.0, 0.1, 100, "dairy", True),
    ("Susu Full Cream", ("susu full", "susu sapi full cream", "full cream milk"), 60, 3.2, 4.8, 3.3, 100, "dairy", False),
    ("Greek Yogurt", ("greek yogurt", "yogurt", "yoghurt"), 59, 10.0, 3.6, 0.4, 100, "dairy", True),
    ("Keju Mozarella", ("keju", "mozarella", "mozarella light"), 280, 28.0, 3.0, 18.0, 100, "dairy", False),
    ("Whey Protein Scoop", ("whey", "whey protein", "protein powder", "scoop whey"), 120, 24.0, 3.0, 1.5, 30, "protein", False),

    # ---- Vegetables (volume eating core) ----------------------------
    ("Bayam", ("bayam", "spinach", "sayur bayam"), 23, 2.9, 3.6, 0.4, 100, "vegetable", True),
    ("Kangkung", ("kangkung", "water spinach", "kangkung rebus"), 20, 2.6, 3.1, 0.3, 100, "vegetable", True),
    ("Sawi Hijau", ("sawi", "sawi hijau", "mustard green"), 20, 2.5, 3.0, 0.3, 100, "vegetable", True),
    ("Brokoli", ("brokoli", "broccoli"), 34, 2.8, 7.0, 0.4, 100, "vegetable", True),
    ("Kembang Kol", ("kembang kol", "cauliflower"), 25, 1.9, 5.0, 0.3, 100, "vegetable", True),
    ("Wortel", ("wortel", "carrot", "wortel rebus"), 35, 0.8, 8.0, 0.2, 100, "vegetable", True),
    ("Tomat", ("tomat", "tomato"), 18, 0.9, 3.9, 0.2, 100, "vegetable", True),
    ("Timun", ("timun", "cucumber", "timun segar"), 16, 0.7, 3.6, 0.1, 100, "vegetable", True),
    ("Selada", ("selada", "lettuce", "selada air"), 15, 1.4, 2.9, 0.2, 100, "vegetable", True),
    ("Kol", ("kol", "cabbage", "kubis"), 25, 1.3, 6.0, 0.1, 100, "vegetable", True),
    ("Tauge", ("tauge", "tauge", "bean sprout"), 30, 3.0, 5.0, 0.2, 100, "vegetable", True),
    ("Paprika", ("paprika", "paprika merah", "pepper"), 31, 1.0, 6.0, 0.3, 100, "vegetable", True),
    ("Jamur Tiram", ("jamur", "jamur tiram", "oyster mushroom"), 33, 3.3, 6.0, 0.3, 100, "vegetable", True),
    ("Jamur Champignon", ("jamur champignon", "champignon", "button mushroom"), 22, 3.1, 3.3, 0.3, 100, "vegetable", True),

    # ---- Fruits ------------------------------------------------------
    ("Pepaya", ("pepaya"), 43, 0.5, 11.0, 0.3, 100, "fruit", True),
    ("Melon", ("melon"), 34, 0.8, 8.0, 0.2, 100, "fruit", True),
    ("Semangka", ("semangka", "watermelon"), 30, 0.6, 7.6, 0.2, 100, "fruit", True),
    ("Jeruk", ("jeruk", "orange"), 47, 0.9, 12.0, 0.1, 100, "fruit", True),
    ("Apel", ("apel", "apple"), 52, 0.3, 14.0, 0.2, 100, "fruit", True),
    ("Pisang", ("pisang", "banana"), 89, 1.1, 23.0, 0.3, 100, "fruit", False),
    ("Mangga", ("mangga", "mango"), 60, 0.8, 15.0, 0.4, 100, "fruit", False),

    # ---- Nuts / fats / oils -----------------------------------------
    ("Kacang Almond", ("almond", "kacang almon"), 579, 21.0, 22.0, 49.0, 100, "fat", False),
    ("Kacang Tanah", ("kacang tanah", "peanut"), 567, 26.0, 16.0, 49.0, 100, "fat", False),
    ("Alpukat", ("alpukat", "avocado"), 160, 2.0, 9.0, 15.0, 100, "fat", False),
    ("Minyak Zaitun", ("minyak zaitun", "olive oil"), 884, 0.0, 0.0, 100.0, 15, "fat", False),
    ("Mentega", ("mentega", "butter"), 717, 0.9, 0.1, 81.0, 15, "fat", False),

    # ---- Restaurant / street food (per portion) ----------------------
    ("Nasi Padang Komplit", ("nasi padang", "padang"), 650, 25.0, 80.0, 25.0, 400, "restaurant", False),
    ("Nasi Ayam Geprek", ("nasi geprek", "geprek nasi"), 550, 30.0, 70.0, 18.0, 350, "restaurant", False),
    ("Bakso Sapi", ("bakso", "bakso sapi", "meatball soup"), 380, 22.0, 35.0, 18.0, 300, "restaurant", False),
    ("Mie Ayam", ("mie ayam", "mi ayam"), 450, 20.0, 60.0, 15.0, 300, "restaurant", False),
    ("Soto Ayam", ("soto", "soto ayam"), 320, 25.0, 30.0, 12.0, 300, "restaurant", False),
    ("Gado-gado", ("gado gado", "gado-gado"), 280, 12.0, 30.0, 14.0, 250, "restaurant", True),
    ("Karedok", ("karedok"), 220, 10.0, 25.0, 11.0, 200, "restaurant", True),
    ("Pecel Lele", ("pecel lele", "lele"), 420, 28.0, 40.0, 20.0, 300, "restaurant", False),
    ("Ayam Bakar Taliwang", ("ayam taliwang", "taliwang"), 380, 35.0, 12.0, 24.00, 300, "restaurant", False),
    ("Nasi Uduk", ("nasi uduk"), 380, 6.0, 55.0, 15.0, 200, "restaurant", False),
    ("Bubur Ayam", ("bubur", "bubur ayam"), 350, 15.0, 50.0, 10.0, 300, "restaurant", False),
    ("Es Teh Manis", ("es teh", "teh manis", "es teh manis"), 90, 0.0, 23.0, 0.0, 250, "drink", False),
    ("Kopi Susu", ("kopi susu", "kopsus"), 120, 2.0, 18.0, 4.0, 200, "drink", False),
    ("Kopi Hitam", ("kopi hitam", "kopi pahit", "americano"), 5, 0.2, 1.0, 0.0, 200, "drink", True),
    ("Jus Alpukat", ("jus alpukat"), 220, 2.0, 30.0, 10.0, 200, "drink", False),
)


def _build() -> list[dict]:
    out: list[dict] = []
    for row in _RAW:
        name, aliases, kcal, prot, carb, fat, portion, cat, volume = row
        out.append(
            {
                "id": name.lower().replace(" ", "-"),
                "name": name,
                "aliases": list(aliases),
                "kcal": kcal,
                "protein_g": prot,
                "carb_g": carb,
                "fat_g": fat,
                "portion_g": portion,
                "category": cat,
                "volume_eating": volume,
            }
        )
    return out


FOODS: list[dict] = _build()

# Fast lookup for the search endpoint
FOODS_BY_ID: dict[str, dict] = {f["id"]: f for f in FOODS}


def search_foods(query: str, limit: int = 12) -> list[dict]:
    """Substring/alias match, ranked: exact-name > alias hit > category.

    Deliberately simple: this is the offline backfill for the AI food
    parser and the results behind the smart search bar.
    """
    q = (query or "").strip().lower()
    if not q:
        return []

    exact, alias, other = [], [], []
    for f in FOODS:
        if q == f["name"].lower():
            exact.append(f)
        elif q in f["name"].lower() or any(q in a for a in f["aliases"]):
            alias.append(f)
        elif q in f["category"]:
            other.append(f)

    return (exact + alias + other)[:limit]


def high_volume_foods(limit: int = 20) -> list[dict]:
    """Foods flagged high-volume / low-kcal (feature #4)."""
    return [f for f in FOODS if f["volume_eating"]][:limit]


# ---- Exercise calorie estimates -------------------------------------
# MET-based: kcal ~= MET * weight_kg * hours. Values per 30 min @ 70 kg.
EXERCISES: tuple[tuple[str, float, int], ...] = (
    ("Jalan Cepat", 4.3, 30),
    ("Lari (10 km/jam)", 9.8, 30),
    ("Bersepeda", 7.5, 30),
    ("Berenang", 8.0, 30),
    ("Angkat Beban", 5.0, 30),
    ("HIIT", 9.0, 30),
    ("Yoga", 3.0, 30),
    ("Bulutangkis", 5.5, 30),
    ("Futsal", 7.0, 30),
    ("Jalan Santai", 3.5, 30),
)


def build_exercises() -> list[dict]:
    """kcal estimate for a 70 kg person doing `duration_min` minutes."""
    return [
        {
            "id": name.lower().replace(" ", "-").replace("(", "").replace(")", ""),
            "name": name,
            "met": met,
            "kcal_per_30min": round(met * 70 * 0.5),
            "duration_min": dur,
        }
        for name, met, dur in EXERCISES
    ]


EXERCISE_LIST: list[dict] = build_exercises()
