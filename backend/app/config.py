"""Centralised configuration. Reads `.env` at the project root.

Kept dependency-free on purpose: the only third-party runtime deps are
fastapi, uvicorn and httpx.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _dotenv(path: Path) -> dict[str, str]:
    """Tiny .env parser (KEY=VALUE, # comments, optional quotes)."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


class Settings:
    def __init__(self) -> None:
        # An explicit process env var wins over .env (the file is the
        # default, not the override) so tests and deploy tools can force a
        # value without editing the project.
        env = {**_dotenv(PROJECT_ROOT / ".env"), **os.environ}

        self.gemini_api_key: str = env.get("GEMINI_API_KEY", "")
        self.gemini_base_url: str = env.get(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai",
        ).rstrip("/")
        self.gemini_model: str = env.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

        self.host: str = env.get("HOST", "127.0.0.1")
        self.port: int = int(env.get("PORT", "8000"))

        self.ai_mode: str = "gemini"

        # Explicit timezone for the app's own day boundaries. Blank means
        # the server's local time. All "today" logic and meal timestamps
        # follow this zone, so the log day rolls at 00:00 local (07:00 UTC).
        tz_name: str = env.get("TZ", "").strip()
        if tz_name:
            os.environ.setdefault("TZ", tz_name)
        self.tz_name: str = tz_name or time.tzname[0]
        self.mongodb_uri: str = env.get("MONGODB_URI", "mongodb://localhost:27017")
        self.db_name: str = env.get("DB_NAME", "nurtra")

        default_db = PROJECT_ROOT / "data" / "defisitku.json"
        self.db_path: str = env.get("DB_PATH", str(default_db))

    @property
    def atria_ready(self) -> bool:
        return False

    @property
    def gemini_ready(self) -> bool:
        """All AI features now use Gemini."""
        return bool(self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


# ---- Local time helpers ------------------------------------------------
# All date logic (the "today" that meals/exercises attach to, the boundary
# that rolls the log over) follows local time, not UTC. These keep the
# naive-datetimes used by the JSON store consistent everywhere.


def local_now() -> datetime:
    """Wall-clock now in the configured zone (naive, no tz suffix).

    zoneinfo resolves TZ against the IANA database. Windows lacks time.tzset,
    so the zone is applied per-call rather than process-wide.
    """
    try:
        return datetime.now(ZoneInfo(get_settings().tz_name)).replace(tzinfo=None)
    except (ZoneInfoNotFoundError, ValueError):
        # Unknown zone name or zoneinfo unavailable: fall back to the OS clock
        # rather than refuse to start.
        return datetime.now().replace(tzinfo=None)


def today_local_iso() -> str:
    """The current log day as a plain YYYY-MM-DD string."""
    return local_now().date().isoformat()
