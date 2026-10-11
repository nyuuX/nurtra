"""Centralised configuration. Reads `.env` at the project root.

Kept dependency-free on purpose: the only third-party runtime deps are
fastapi, uvicorn and httpx.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

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
        env = {**os.environ, **_dotenv(PROJECT_ROOT / ".env")}

        self.atria_api_key: str = env.get("ATRIA_API_KEY", "")
        self.atria_base_url: str = env.get(
            "ATRIA_BASE_URL", "https://api.atria-asi.ai/v1"
        ).rstrip("/")
        self.atria_model: str = env.get("ATRIA_MODEL", "Atria-Dawn-Preview")

        self.host: str = env.get("HOST", "127.0.0.1")
        self.port: int = int(env.get("PORT", "8000"))

        # "atria" = call the real API, "demo" = deterministic local fallbacks
        self.ai_mode: str = env.get("AI_MODE", "atria").lower()

        default_db = PROJECT_ROOT / "data" / "defisitku.json"
        self.db_path: str = env.get("DB_PATH", str(default_db))

    @property
    def atria_ready(self) -> bool:
        return bool(self.atria_api_key) and self.ai_mode == "atria"


@lru_cache
def get_settings() -> Settings:
    return Settings()
