"""Session tokens — stdlib-only, no JWT dependency.

A token is `base64(user_email).signature` where the signature is an
HMAC-SHA256 of the payload using a server secret. The secret is generated
once and persisted next to the JSON db, so tokens survive restarts.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

from .config import get_settings

SECRET_LEN = 32
TOKEN_TTL = 60 * 60 * 24 * 30  # 30 days


def _secret_path() -> Path:
    return Path(get_settings().db_path).parent / ".session_secret"


def _get_secret() -> bytes:
    # 1. Env var wins (required on read-only serverless filesystems).
    env_secret = os.environ.get("SESSION_SECRET")
    if env_secret:
        return hashlib.sha256(env_secret.encode("utf-8")).digest()
    # 2. Persisted file (local dev). Serverless = read-only, so never mkdir.
    path = _secret_path()
    try:
        if path.exists():
            return base64.b64decode(path.read_bytes())
        secret = secrets.token_bytes(SECRET_LEN)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64encode(secret))
        return secret
    except OSError:
        # Read-only filesystem without SESSION_SECRET set: ephemeral secret.
        # Tokens live for the function instance only; logins re-issue them.
        return secrets.token_bytes(SECRET_LEN)


def _sign(payload: bytes) -> str:
    return base64.b64encode(
        hmac.new(_get_secret(), payload, hashlib.sha256).digest()
    ).decode()


def create_token(email: str) -> str:
    """Issue a session token for a user."""
    issued = int(time.time())
    payload = f"{email}|{issued}".encode("utf-8")
    b64 = base64.b64encode(payload).decode()
    return f"{b64}.{_sign(payload)}"


def verify_token(token: str | None) -> str | None:
    """Return the user email if the token is valid and not expired."""
    if not token:
        return None
    parts = token.split(".", 1)
    if len(parts) != 2:
        return None
    b64, sig = parts
    try:
        payload = base64.b64decode(b64)
    except Exception:
        return None

    expected = _sign(payload)
    if not hmac.compare_digest(sig, expected):
        return None

    try:
        email, issued = payload.decode("utf-8").rsplit("|", 1)
        issued = int(issued)
    except Exception:
        return None

    if time.time() - issued > TOKEN_TTL:
        return None
    return email
