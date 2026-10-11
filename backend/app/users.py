"""User store + password hashing for the local JSON backend.

Passwords are hashed with hashlib.pbkdf2_hmac with a per-user salt —
deliberately stdlib-only (no passlib/bcrypt dependency to install).

A "user" owns a slice of the JSON store: meals, exercises, weights,
profile, favorites. Anonymous users keep using the shared demo data so the
app stays fully usable before signup.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from pathlib import Path

from .config import get_settings

_lock = threading.Lock()
ITERATIONS = 200_000


def _db_path() -> Path:
    return Path(get_settings().db_path)


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """PBKDF2-SHA256. Returns (salt_b64, hash_b64)."""
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return base64.b64encode(salt).decode(), base64.b64encode(dk).decode()


def _verify_password(password: str, salt_b64: str, hash_b64: str) -> bool:
    try:
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except Exception:
        return False
    _, computed_b64 = _hash_password(password, salt)
    return hmac.compare_digest(
        base64.b64decode(computed_b64), expected
    )


# ---- User records ----------------------------------------------------------

def _load_db() -> dict:
    from .store import load

    data = load()
    data.setdefault("users", {})
    return data


def _save_db(data: dict) -> None:
    from .store import save

    save(data)


def find_user(email: str) -> dict | None:
    """Return the user record for an email, or None."""
    data = _load_db()
    return data["users"].get(email.lower())


def create_user(email: str, password: str, name: str = "") -> dict:
    """Create a user. Raises ValueError if the email is already taken."""
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("Email tidak valid")
    if len(password) < 6:
        raise ValueError("Password minimal 6 karakter")

    data = _load_db()
    with _lock:
        if email in data["users"]:
            raise ValueError("Email sudah terdaftar")

        salt_b64, hash_b64 = _hash_password(password)
        now = int(time.time())
        user = {
            "email": email,
            "name": name.strip() or email.split("@")[0],
            "salt": salt_b64,
            "password_hash": hash_b64,
            "created_at": now,
            # Per-user data (populated on first login / signup)
            "profile": None,
            "days": [],
            "favorites": [],
            "recent_searches": [],
        }
        data["users"][email] = user
        _save_db(data)
    return user


def verify_credentials(email: str, password: str) -> dict | None:
    """Return the user if the email+password match, else None."""
    user = find_user(email)
    if not user:
        return None
    if not _verify_password(password, user["salt"], user["password_hash"]):
        return None
    return user


def update_user_profile(email: str, profile: dict) -> None:
    data = _load_db()
    with _lock:
        user = data["users"].get(email.lower())
        if user:
            user["profile"] = profile
            _save_db(data)
