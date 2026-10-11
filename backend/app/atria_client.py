"""Shared Atria Dawn transport.

The model is TEXT-ONLY: every request leaves this file as a JSON chat
completion. Never send binary/image data to the Atria endpoint.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from .config import get_settings

log = logging.getLogger("defisitku.atria")

settings = get_settings()


def chat(
    messages: list[dict],
    temperature: float = 0.4,
    max_tokens: int = 1800,
    timeout: float = 180.0,
) -> str | None:
    """One Atria Dawn chat completion. Returns assistant text, or None on
    any transport/HTTP failure so callers can degrade to a local fallback."""
    payload = {
        "model": settings.atria_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {settings.atria_api_key}",
        "Content-Type": "application/json",
    }
    url = f"{settings.atria_base_url}/chat/completions"
    # Atria Dawn is a reasoning model: the weekly-insights prompt can take a
    # while, so allow generous headroom. Callers still degrade gracefully.
    timeout_s = max(timeout, 240.0)
    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.post(url, headers=headers, json=payload)
    except Exception as exc:
        log.warning("atria transport error: %s", exc)
        return None

    if resp.status_code != 200:
        log.warning("atria non-200: %s %s", resp.status_code, resp.text[:300])
        return None

    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    return (choice.get("message") or {}).get("content")


def extract_json(text: str | None) -> Any:
    """Pull the first JSON object/array out of a model response.

    Deliberately forgiving: models sometimes wrap JSON in ```json fences or
    add stray prose, and one bad reply should not break the dashboard.
    """
    if not text:
        return None
    text = text.strip()
    # The fence removal was originally for Atria, but Gemini 3.x also wraps
    # its JSON in ```json even when asked not to, and the trailing fence
    # lands before the last "}" — so the balanced-brace fallback below is
    # what actually saves these replies.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # A trailing ``` can appear mid-document after the JSON itself (a
    # closing fence plus more text); strip any fence still present.
    text = text.replace("```", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fall back to the first balanced {...} region. Prefer an object over an
    # array: a fenced object whose closing brace is missing mid-document can
    # still match an inner array first, which would hand callers a list where
    # they expect a dict. Object-first keeps that ordering correct.
    for pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                continue
    return None


def num(value: Any) -> float:
    """Coerce anything numeric-ish to float; everything else to 0.0."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
