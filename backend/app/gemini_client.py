"""Gemini transport for the photo -> nutrition feature.

Atria Dawn is text-only, so this is a separate OpenAI-compatible client.
Only this module sends image data; atria_client.py stays binary-free.

Gemini 3.x is a reasoning model on a tight free-tier RPM budget, so every
call is bounded by max_tokens (an unbounded reply burns a whole minute of
quota reasoning about a photo) and retried once on transient 429/503.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .config import get_settings

log = logging.getLogger("defisitku.gemini")

settings = get_settings()

# Gemini returns these when the free tier is momentarily saturated; the
# guidance from the API itself is to retry shortly after.
_RETRYABLE = {429, 503}


def _post(payload: dict, timeout: float) -> tuple[httpx.Response | None, str | None]:
    url = f"{settings.gemini_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.gemini_api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            return client.post(url, headers=headers, json=payload), None
    except Exception as exc:
        return None, f"transport error: {exc}"


def vision_chat(
    prompt: str,
    image_b64: str,
    mime_type: str = "image/jpeg",
    temperature: float = 0.2,
    max_tokens: int = 900,
    timeout: float = 120.0,
) -> str | None:
    """Send one image + prompt, return the assistant text or None.

    None is the signal to the caller to degrade to a local fallback.
    """
    payload = {
        "model": settings.gemini_model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                    },
                ],
            }
        ],
    }

    for attempt in range(2):
        resp, err = _post(payload, timeout)
        if err:
            log.warning("gemini transport error: %s", err)
            return None
        if resp.status_code == 200:
            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            content = (choice.get("message") or {}).get("content")
            if content:
                return content
            log.warning("gemini: empty content in 200 response")
            return None
        if resp.status_code in _RETRYABLE and attempt == 0:
            log.info("gemini %s, retrying in 4s", resp.status_code)
            time.sleep(4)
            continue
        log.warning("gemini non-200: %s %s", resp.status_code, resp.text[:300])
        return None
    return None


def text_chat(
    messages: list[dict],
    temperature: float = 0.4,
    max_tokens: int = 1800,
    timeout: float = 180.0,
) -> str | None:
    """One Gemini chat completion over text content. Returns assistant text
    or None on any transport/HTTP failure so callers can degrade."""
    payload = {
        "model": settings.gemini_model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    for attempt in range(2):
        resp, err = _post(payload, timeout)
        if err:
            log.warning("gemini transport error: %s", err)
            return None
        if resp.status_code == 200:
            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            content = (choice.get("message") or {}).get("content")
            if content:
                return content
            log.warning("gemini: empty content in 200 response")
            return None
        if resp.status_code in _RETRYABLE and attempt == 0:
            log.info("gemini %s, retrying in 4s", resp.status_code)
            time.sleep(4)
            continue
        log.warning("gemini non-200: %s %s", resp.status_code, resp.text[:300])
        return None
    return None
