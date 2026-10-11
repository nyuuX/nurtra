"""One-off migration: backfill `id` on stored exercises that predate it.

Existing data/defisitku.json files were seeded without an id on exercise
entries, which made DELETE /api/exercises/{id} match nothing (404).
Run once:  python -m tools.backfill_exercise_ids
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.store import load, save  # noqa: E402


def backfill() -> int:
    data = load()
    fixed = 0
    for day in data.get("days", []):
        for ex in day.get("exercises", []):
            if not ex.get("id"):
                ex["id"] = f"migrated-{fixed + 1}"
                if "duration_min" not in ex:
                    ex["duration_min"] = 30
                fixed += 1
    if fixed:
        save(data)
    return fixed


if __name__ == "__main__":
    count = backfill()
    print(f"backfilled {count} exercise entries with an id")
