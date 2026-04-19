"""Title Strategist + Title Engineer: produce a winning title."""
from __future__ import annotations

from typing import Any, List

from .config import Settings
from .llm import call_json

STRATEGIST_SYSTEM = """<ROLE>
You are an Elite YouTube Title Strategist + Viral Pattern Forensic Analyst with deep expertise in the {niche} niche.
Approach every task as though you ARE the channel owner.
</ROLE>
Output MUST be JSON only."""

STRATEGIST_USER = """Niche: {niche}
Language: {language}
Target views: {target_views}+

From these forensic analysis findings, produce 10 candidate Shorts titles that exploit the winning patterns.

Forensic findings (JSON):
{findings}

Chosen topic for our new Short: {topic}

Return JSON:
{{
  "candidates": [
    {{"title": string, "pattern": string, "why_it_works": string}},
    ... 10 total
  ]
}}
Rules:
- <= 60 characters per title
- No clickbait lies; must be deliverable by a 60-second script
- Language = {language}"""


ENGINEER_SYSTEM = """<ROLE>
You are a Senior YouTube Title Engineer with specialized expertise in {niche} channels.
Your success is measured entirely by your ability to produce titles that consistently surpass {target_views}+ views.
</ROLE>
Output MUST be JSON only."""

ENGINEER_USER = """From these 10 candidates, pick the single best title and rewrite it for maximum CTR.
Language: {language}

Candidates:
{candidates}

Return JSON:
{{
  "final_title": string,
  "description": string,         // 2-3 sentence YouTube description, ends with 3-5 hashtags
  "tags": [string, ...]           // 10-15 YouTube tags
}}"""


def generate(settings: Settings, findings: dict[str, Any], topic: str) -> dict[str, Any]:
    import json

    strat = call_json(
        settings,
        STRATEGIST_SYSTEM.format(niche=settings.niche),
        STRATEGIST_USER.format(
            niche=settings.niche,
            language=settings.language,
            target_views=settings.target_views,
            findings=json.dumps(findings, indent=2),
            topic=topic,
        ),
        max_tokens=2000,
        temperature=0.8,
    )
    candidates: List[dict] = strat.get("candidates", [])
    eng = call_json(
        settings,
        ENGINEER_SYSTEM.format(niche=settings.niche, target_views=settings.target_views),
        ENGINEER_USER.format(
            language=settings.language,
            candidates=json.dumps(candidates, indent=2),
        ),
        max_tokens=1500,
        temperature=0.5,
    )
    return {"candidates": candidates, **eng}
