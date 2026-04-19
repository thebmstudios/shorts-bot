"""Shared Claude client."""
from __future__ import annotations

import json
import re
from typing import Any

from anthropic import Anthropic

from .config import Settings

MODEL = "claude-sonnet-4-5-20250929"


def get_client(settings: Settings) -> Anthropic:
    return Anthropic(api_key=settings.anthropic_api_key)


def call(settings: Settings, system: str, user: str, *, max_tokens: int = 4000, temperature: float = 0.7) -> str:
    client = get_client(settings)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
    return "".join(parts).strip()


def call_json(settings: Settings, system: str, user: str, *, max_tokens: int = 4000, temperature: float = 0.4) -> Any:
    """Call Claude and parse a JSON object/array from the response."""
    text = call(settings, system, user, max_tokens=max_tokens, temperature=temperature)
    match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    payload = match.group(1) if match else text
    brace = payload.find("{")
    bracket = payload.find("[")
    candidates = [i for i in (brace, bracket) if i != -1]
    if candidates:
        payload = payload[min(candidates):]
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LLM did not return valid JSON:\n{text}") from exc
