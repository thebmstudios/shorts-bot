"""Script writer: produce a 60-second narration script."""
from __future__ import annotations

import json
from typing import Any

from .config import Settings
from .llm import call_json

SYSTEM = """You are a top-tier YouTube Shorts ghostwriter for the {niche} niche.
You write 60-second narration scripts (~130 words) optimized for retention.
You are also a careful historian: you NEVER include figures, dates, or events
that are not directly part of the specific topic you were given. You would
rather omit a beat than invent a connection between unrelated empires or eras.
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

FACTUAL ACCURACY (this matters more than retention — wrong facts get the channel flagged):
- Every named person, place, battle, or date you mention MUST be directly part of THIS topic's actual events. No exceptions.
- DO NOT drag in famous figures from other eras for color. Bad: a Byzantine-emperor script that mentions Timur because both are "medieval Asia" — Timur fought Bayezid (Ottoman), not Byzantium. Bad: a Roman script that name-drops Genghis Khan for atmosphere.
- If you're not certain a person was at the event / in the same century / in the same empire as the topic — leave them out. Use "an advisor", "a rival general" instead of inventing a name.
- Only use dates, body counts, and quotes that are well-attested. If you don't know the exact number, use a range ("tens of thousands") not a fabricated specific.
- Do not invent dialogue. Do not invent letters or speeches.
- Geography must match: don't move a battle to the wrong river or city.
- When in doubt, write less rather than make it up. A vague-but-true line beats a vivid-but-wrong one.

CATEGORY-SPECIFIC TONE (apply based on the topic type):
- HISTORY topics: use the standard "modern scientists debunk the myth" beat where appropriate.
- REAL-EVENTS topics (true crime, modern cover-ups, survival, disasters): anchor every claim in documented record — court cases, government reports, named witnesses, dates. Treat the audience like adults who want the actual sequence of events, not a true-crime podcast voice.
- PARANORMAL topics (hauntings, UFOs, unexplained disappearances, cryptids): MUST be a documented real case (named witnesses, date, location, official report or media coverage). Narrate WHAT WITNESSES REPORTED and WHAT INVESTIGATORS FOUND. Then briefly mention the official/skeptical explanation IF ONE EXISTS — but do NOT smugly debunk. The viewer is here for unease; leave the mystery open. Do NOT invent fake ghost stories or campfire-style fiction.

LOGICAL CONSISTENCY (HARD RULE — violations get the script rejected):
- Track whether the subject is alive or dead at every moment of the narrative. Once you state someone has died, been killed, executed, beheaded, strangled, drowned, or otherwise stopped breathing, they CANNOT then be described as "skinned alive", "burned alive", "buried alive", "boiled alive", or any "[verb] alive" construction.
- If a historical source says the person was tortured before dying, narrate the torture FIRST, then the death. Never reverse the order.
- If the source is ambiguous about whether the act was pre- or post-mortem (e.g., Valerian's flaying), say "his body was skinned" or "his corpse was flayed" — do NOT use "alive".
- A captured person is alive until the script explicitly kills them. After death, only post-mortem language is allowed (corpse, body, remains, skull, head).

BANNED PHRASES (do not use these — they are overused or contradictory):
- "problem solved" / "issue resolved" / "and that was that" / "job done" — banned entirely.
- "X alive" applied to an already-dead character (see Logical Consistency rule).

Return JSON:
{{
  "narration": string,              // the full script, plain prose, no stage directions
  "sentences": [string, ...],        // same content split into narration-ready sentences
  "b_roll_keywords": [string, ...]   // 6-10 SPECIFIC NAMED ENTITIES from the script
}}

CRITICAL — b_roll_keywords rules (this drives image search; bad keywords = wrong images):
- ONLY specific named entities that actually appear in your narration: person names, battle names, city/place names, empire/dynasty names, specific events with dates.
- GOOD examples: "Suleiman the Magnificent", "Battle of Mohács 1526", "Janissary corps", "Topkapi Palace", "Mehmed II portrait", "Hagia Sophia"
- BAD examples (NEVER USE): "war", "soldier", "ancient warrior", "old map", "history", "sword", "castle", "empire", "battlefield" — these are generic and pull random unrelated images.
- If your script mentions a person/place/battle, that exact name MUST be a keyword.
- Each keyword must be Wikipedia-searchable as a real article title or close to one.
- Order matters: most-central entity first."""


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
