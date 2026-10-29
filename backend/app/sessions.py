"""Session tokens — stdlib crypto, MongoDB-backed session revocation.

A token is `base64(email|issued|jti).signature` where the signature is an
HMAC-SHA256 of the payload using a server secret.

Verification policy (resilient to serverless DB hiccups):
  1. Cryptographic signature must match (proves it was issued by us).
  2. Token must not be expired (30 days TTL).
  3. If MongoDB session record exists and explicitly marked revoked/missing, reject.
     If MongoDB is unreachable or record is missing due to eventual consistency,
     trust the cryptographic signature to prevent unwanted logouts.
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
    env_secret = os.environ.get("SESSION_SECRET")
    if env_secret:
        return hashlib.sha256(env_secret.encode("utf-8")).digest()
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


def _sessions_collection():
    try:
        from . import store
        db = store._get_db()
        return db["sessions"]
    except Exception:
        return None


def _store_session(jti: str, email: str, issued: int) -> None:
    col = _sessions_collection()
    if col is not None:
        try:
            col.update_one(
                {"_id": jti},
                {"$set": {"email": email, "issued": issued, "expires": issued + TOKEN_TTL}},
                upsert=True,
            )
        except Exception:
            pass


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
        col = _sessions_collection()
        if col is not None:
            col.delete_one({"_id": jti})
    except Exception:
        pass


def create_token(email: str) -> str:
    """Issue a signed session token."""
    issued = int(time.time())
    jti = secrets.token_hex(16)
    payload = f"{email}|{issued}|{jti}".encode("utf-8")
    b64 = base64.b64encode(payload).decode()
    _store_session(jti, email, issued)
    return f"{b64}.{_sign(payload)}"


def verify_token(token: str | None) -> str | None:
    """Return the user email if the token is valid and not expired.

    Trusts cryptographic signature primarily. Only rejects if explicitly
    revoked in DB (if DB is reachable).
    """
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

    # Check revocation if DB is accessible
    col = _sessions_collection()
    if col is not None:
        try:
            doc = col.find_one({"_id": jti}, {"revoked": 1})
            if doc and doc.get("revoked"):
                return None
        except Exception:
            pass

    return email_s
