"""Session tokens — stdlib crypto, MongoDB-backed session store.

A token is `base64(email|issued|jti).signature` where the signature is an
HMAC-SHA256 of the payload using a server secret. The `jti` is a random
session id whose record lives in the `sessions` MongoDB collection, so
sessions survive across serverless instances (Vercel cold starts) and can
be revoked server-side.

Fallbacks keep local dev and Mongo outages working:
  * SESSION_SECRET env var wins over the persisted file secret.
  * If Mongo is unreachable, a structurally valid signed token is still
    accepted (offline-first), it just cannot be revoked.
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
    # 2. Persisted file (local dev).
    path = _secret_path()
    try:
        if path.exists():
            return base64.b64decode(path.read_bytes())
        secret = secrets.token_bytes(SECRET_LEN)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64encode(secret))
        return secret
    except OSError:
        return secrets.token_bytes(SECRET_LEN)


def _sign(payload: bytes) -> str:
    return base64.b64encode(
        hmac.new(_get_secret(), payload, hashlib.sha256).digest()
    ).decode()


# ---- MongoDB session store ------------------------------------------------

def _sessions_collection():
    from . import store  # late import: store pulls in pymongo/certifi
    db = store._get_db()
    return db["sessions"]


def _store_session(jti: str, email: str, issued: int) -> None:
    try:
        _sessions_collection().update_one(
            {"_id": jti},
            {"$set": {"email": email, "issued": issued, "expires": issued + TOKEN_TTL}},
            upsert=True,
        )
    except Exception:
        pass  # offline-first: token alone is still verifiable


def _session_is_known(jti: str) -> bool:
    try:
        return _sessions_collection().find_one({"_id": jti}, {"_id": 1}) is not None
    except Exception:
        return True  # Mongo unreachable: don't hard-block logins


def revoke_session(token: str | None) -> None:
    """Invalidate a token server-side (logout)."""
    if not token:
        return
    parts = token.split(".", 1)
    if len(parts) != 2:
        return
    try:
        payload = base64.b64decode(parts[0]).decode("utf-8")
        _email, _issued, jti = payload.rsplit("|", 2)
        _sessions_collection().delete_one({"_id": jti})
    except Exception:
        pass


# ---- Token API ------------------------------------------------------------

def create_token(email: str) -> str:
    """Issue a signed, MongoDB-recorded session token for a user."""
    issued = int(time.time())
    jti = secrets.token_hex(16)
    payload = f"{email}|{issued}|{jti}".encode("utf-8")
    b64 = base64.b64encode(payload).decode()
    _store_session(jti, email, issued)
    return f"{b64}.{_sign(payload)}"


def verify_token(token: str | None) -> str | None:
    """Return the user email if the token is valid, signed, and not expired."""
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
        decoded = payload.decode("utf-8")
        email_s, issued_s, jti = decoded.rsplit("|", 2)
        issued = int(issued_s)
    except Exception:
        return None

    if time.time() - issued > TOKEN_TTL:
        return None
    if not _session_is_known(jti):
        return None
    return email_s
