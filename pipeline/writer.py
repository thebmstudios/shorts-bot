"""Script writer: produce a 60-second narration script."""
from __future__ import annotations

import json
from typing import Any

from .config import Settings
from .llm import call_json

SYSTEM = """You are a top-tier YouTube Shorts ghostwriter for the {niche} niche.
You write 60-second narration scripts (~130 words) optimized for retention.
Apply the provided forensic patterns faithfully.
Output MUST be JSON only."""

USER = """Title: {title}
Language: {language}
Target duration: 55-60 seconds when read aloud at NATURAL narration pace.
Write 120-135 words total (strict).

Forensic patterns to apply:
{findings}

Rules:
- Open with a hook in the first sentence (<= 10 words) that creates an information gap.
- Body: deliver the payoff with 4-6 tight beats, concrete names, dates, numbers, visual details.
- Include at least one "here's the crazy part" / "but here's where it gets worse" escalation pivot.
- Close: a surprising final line that makes viewers rewatch or comment.
- No filler ("in this video", "today we will"). No self-reference.
- Short, punchy sentences. Active voice.
- MUST be 120-135 words — count them. Not less, not more.
- Language = {language}.

Return JSON:
{{
  "narration": string,              // the full script, plain prose, no stage directions
  "sentences": [string, ...],        // same content split into narration-ready sentences
  "b_roll_keywords": [string, ...]   // 6-10 stock-footage keywords (people, places, events)
}}"""


def write_script(settings: Settings, title: str, findings: dict[str, Any]) -> dict[str, Any]:
    return call_json(
        settings,
        SYSTEM.format(niche=settings.niche),
        USER.format(
            title=title,
            language=settings.language,
            findings=json.dumps(findings, indent=2),
        ),
        max_tokens=2500,
        temperature=0.75,
    )
