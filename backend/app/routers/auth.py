"""Auth endpoints: signup, login, logout, current session."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from .. import sessions, store, users

router = APIRouter()


def _set_session_cookie(resp: Response, token: str) -> None:
    # httponly so JS can't read it (XSS), samesite for CSRF hygiene.
    # `secure` must be True on HTTPS (Vercel); browsers drop a secure=False
    # cookie set over https in some flows, which logged users straight back out.
    is_secure = os.environ.get("VERCEL") == "1" or os.environ.get("FORCE_SECURE_COOKIE") == "1"
    resp.set_cookie(
        key="dk_session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=sessions.TOKEN_TTL,
        path="/",
    )


@router.post("/signup")
def signup(body: dict, response: Response) -> dict:
    email = str(body.get("email") or "")
    password = str(body.get("password") or "")
    name = str(body.get("name") or "")

    try:
        user = users.create_user(email, password, name)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    token = sessions.create_token(user["email"])
    _set_session_cookie(response, token)
    return {
        "user": {"email": user["email"], "name": user["name"]},
        "token": token,
    }


@router.post("/login")
def login(body: dict, response: Response) -> dict:
    login_id = str(body.get("login") or body.get("email") or "")
    password = str(body.get("password") or "")

    user = users.verify_credentials(login_id, password)
    if not user:
        raise HTTPException(401, "Email, username, atau password salah")

    token = sessions.create_token(user["email"])
    _set_session_cookie(response, token)
    return {
        "user": {"email": user["email"], "name": user["name"]},
        "token": token,
    }


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    sessions.revoke_session(request.cookies.get("dk_session"))
    response.delete_cookie("dk_session", path="/")
    return {"ok": True}


@router.get("/me")
def current_user(request: Request) -> dict:
    """Returns the logged-in user, or null for anonymous."""
    token = request.cookies.get("dk_session")
    email = sessions.verify_token(token)
    if not email:
        return {"user": None}
    user = users.find_user(email)
    if not user:
        return {"user": None}
    return {"user": {"email": user["email"], "name": user["name"]}}


# ---- Anonymous <-> user data migration -----------------------------------

@router.post("/migrate-anonymous")
def migrate_anonymous(request: Request) -> dict:
    """Adopt the anonymous demo data into the logged-in user's account.

    Called after first signup so food logs made before signing up are not lost.
    Idempotent: only runs once per user.
    """
    from .. import store

    token = request.cookies.get("dk_session")
    email = sessions.verify_token(token)
    if not email:
        raise HTTPException(401, "Belum login")

    data = store.load()
    user = data.setdefault("users", {}).get(email)
    if not user:
        raise HTTPException(404, "User tidak ditemukan")

    # Only migrate once, and only if the anonymous data was actually modified by the user
    if not data.get("anonymous_dirty") or user.get("days") or user.get("migrated"):
        return {"ok": True, "migrated": False}

    user["profile"] = data.get("profile")
    user["days"] = data.get("days", [])
    user["favorites"] = data.get("favorites", [])
    user["recent_searches"] = data.get("recent_searches", [])
    user["migrated"] = True
    store.save(data)

    return {"ok": True, "migrated": True}
