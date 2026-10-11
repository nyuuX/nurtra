"""Resolve the current request to a user's data slice.

Every data endpoint accepts an optional session cookie. Logged-in users get
their own {profile, days, favorites, recent_searches}; anonymous users keep
using the shared demo slice so the app is fully functional pre-signup.

This is the single seam between auth and the rest of the app: routers ask
for a DataContext and never touch `store.load()` directly.
"""

from __future__ import annotations

import threading
from typing import Any

from fastapi import Request

from . import sessions, store, users

_lock = threading.Lock()

ANONYMOUS = "__anonymous__"


class DataContext:
    """A view over one user's data with load/save semantics."""

    def __init__(self, email: str | None) -> None:
        self.email = email
        self.is_anonymous = email is None

    # ---- Data access --------------------------------------------------------

    def load(self) -> dict:
        """Return the full DB doc with `self.key` as the active slice."""
        return store.load()

    def _slice_key(self) -> str:
        return ANONYMOUS if self.is_anonymous else self.email

    def user_data(self, db: dict) -> dict:
        """Return (and lazily create) this user's data slice."""
        if self.is_anonymous:
            return db  # anonymous: the top-level demo keys

        users_table = db.setdefault("users", {})
        user = users_table.get(self.email)
        if user is None:
            # Token is valid but the user row is gone — treat as anonymous
            raise KeyError(self.email)
        user.setdefault("days", [])
        user.setdefault("favorites", [])
        user.setdefault("recent_searches", [])
        user.setdefault("profile", None)
        return user

    def save(self, db: dict) -> None:
        store.save(db)

    # ---- Profile ------------------------------------------------------------

    def get_profile(self) -> dict:
        return self.user_data(self.load()).get("profile") or {}

    def set_profile(self, profile: dict) -> None:
        with _lock:
            db = self.load()
            self.user_data(db)["profile"] = profile
            self.save(db)

    # ---- Days / meals --------------------------------------------------------

    def get_or_create_day(self, db: dict, date: str) -> dict:
        data = self.user_data(db)
        for d in data.get("days", []):
            if d.get("date") == date:
                return d
        day = {"date": date, "meals": [], "exercises": [], "weight_kg": None}
        data.setdefault("days", []).append(day)
        return day

    def find_day(self, date: str) -> dict | None:
        for d in self.user_data(self.load()).get("days", []):
            if d.get("date") == date:
                return d
        return None

    # ---- Favorites & searches ------------------------------------------------

    def get_favorites(self) -> list[dict]:
        return self.user_data(self.load()).get("favorites", [])

    def add_favorite(self, fav: dict) -> None:
        with _lock:
            db = self.load()
            self.user_data(db).setdefault("favorites", []).append(fav)
            self.save(db)

    def delete_favorite(self, fav_id: str) -> bool:
        with _lock:
            db = self.load()
            data = self.user_data(db)
            before = len(data.get("favorites", []))
            data["favorites"] = [
                f for f in data.get("favorites", []) if f.get("id") != fav_id
            ]
            if len(data["favorites"]) == before:
                return False
            self.save(db)
            return True

    def push_recent_search(self, query: str, limit: int = 8) -> None:
        if not query.strip():
            return
        with _lock:
            db = self.load()
            data = self.user_data(db)
            recents = [s for s in data.get("recent_searches", []) if s != query.strip()]
            recents.insert(0, query.strip())
            data["recent_searches"] = recents[:limit]
            self.save(db)


def from_request(request: Request) -> DataContext:
    """Resolve the session cookie (or Authorization header) to a context."""
    token = request.cookies.get("dk_session")
    if not token:
        # Also accept a bearer token for API clients
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            token = header[7:].strip()
    email = sessions.verify_token(token)
    if not email:
        return DataContext(None)
    if not users.find_user(email):
        return DataContext(None)
    return DataContext(email)


def require_user(request: Request) -> str:
    """Dependency for endpoints that must not be anonymous."""
    ctx = from_request(request)
    if ctx.is_anonymous:
        from fastapi import HTTPException

        raise HTTPException(401, "Login diperlukan")
    return ctx.email
