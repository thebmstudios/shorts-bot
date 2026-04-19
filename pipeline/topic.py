"""Pick a fresh topic based on forensic findings."""
from __future__ import annotations

from typing import Any

from .config import Settings
from .llm import call_json

SYSTEM = """You are a content strategist for a {niche} Shorts channel.
Output MUST be JSON only."""

USER = """Given these forensic findings and the topics competitors already covered, propose ONE fresh, high-potential {niche} topic for our next 60-second Short.
Language: {language}

Findings:
{findings}

Return JSON:
{{
  "topic": string,                  // 1-line topic specific enough to script (include names/dates)
  "angle": string,                  // the hook/angle that differentiates it
  "why": string                     // why this will beat competitors
}}"""


def choose_topic(settings: Settings, findings: dict[str, Any]) -> dict[str, Any]:
    import json as _json
    return call_json(
        settings,
        SYSTEM.format(niche=settings.niche),
        USER.format(
            niche=settings.niche,
            language=settings.language,
            findings=_json.dumps(findings, indent=2),
        ),
        max_tokens=800,
        temperature=0.9,
    )
