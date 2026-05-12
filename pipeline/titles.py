"""Title Strategist + Engineer: produce a curiosity-gap title with no spoilers.

US-audience Shorts optimization:
  - Under 50 characters
  - NO outcome words (died, killed, won, escaped, survived, executed)
  - NO full names + full action + result format
  - Must use one of 5 approved templates (pronoun-mystery, number+gap,
    negation hook, year+stake, question hook)
  - The title hints; the video reveals.
"""
from __future__ import annotations

from typing import Any, List

from .config import Settings
from .llm import call_json

STRATEGIST_SYSTEM = """<ROLE>
You are an Elite YouTube Shorts Title Strategist for a US audience.
Your single job is to produce CURIOSITY-GAP titles. Spoilers in titles are
the #1 reason Shorts under-perform — you NEVER let a title resolve the story.
</ROLE>
Output MUST be JSON only."""

STRATEGIST_USER = """Niche: {niche}
Language: {language}
Audience: United States (Eastern Time mainstream)
Target views: {target_views}+

Chosen topic for our new Short:
{topic}

Forensic findings (style only — do NOT copy outcomes into the title):
{findings}

Produce 10 candidate Shorts titles for this topic. Each title MUST use ONE of
these 5 templates (label which template you used):

T1 — PRONOUN + MYSTERY NOUN
   "His Last Letter Wasn't Sent"
   "Their Bodies Were Never Found"
   "Her Final Order Made No Sense"

T2 — NUMBER + MISSING CONTEXT
   "7 Doctors. One Survivor."
   "9 Climbers. No Explanation."
   "11 Witnesses. One Story."

T3 — NEGATION HOOK
   "Nobody Survived His Room"
   "Nothing Was Left Of The Camp"
   "No One Knew His Real Name"

T4 — YEAR + CRYPTIC STAKE
   "1520: One Mistake Ended An Empire"
   "1959: Something Was On That Mountain"
   "1922: The Tomb They Couldn't Close"

T5 — QUESTION HOOK
   "Why Did The Sultan Trust Him?"
   "What Walked Through That Camp?"
   "Why Was His Coffin Sealed Three Times?"

HARD BANS — automatic rejection:
- The title contains any of: died, killed, won, escaped, survived, executed,
  beheaded, murdered, slaughtered, conquered, destroyed, defeated.
- The title states the outcome (e.g., "Sultan Killed 7 Doctors Then Died From The 8th"
  is BANNED — it spoils the entire story).
- The title gives the famous person's full name AND their famous deed in the same line.
- Over 50 characters.
- All caps. (Title Case only.)
- Emojis.

CURIOSITY RULES:
- The title must make a US viewer ask one specific question they CANNOT answer
  from the title alone. Test: read the title, can you predict the ending? If yes,
  rewrite.
- Lead with pronoun, number, negation, year, or question word. Never lead with
  a person's name unless they're obscure enough that the name itself is a hook.
- One specific detail (a number, an object, a year, a place) that the reader
  cannot place without watching.

Return JSON:
{{
  "candidates": [
    {{"title": string, "template": "T1"|"T2"|"T3"|"T4"|"T5", "curiosity_question": string}},
    ... 10 total
  ]
}}"""


ENGINEER_SYSTEM = """<ROLE>
You are a Senior YouTube Shorts Title Engineer optimizing for a US audience.
You pick the title with the strongest CURIOSITY GAP and the cleanest swipe-stop
appeal. You will reject any candidate that spoils the story or breaks the rules.
</ROLE>
Output MUST be JSON only."""

ENGINEER_USER = """From these 10 candidates, pick the single best one for a US
Shorts audience. Then write a description and tags.

Selection priority (in order):
  1. No spoiler (cannot predict the ending from the title)
  2. Under 50 characters
  3. Uses an approved template (T1-T5)
  4. Specific concrete detail (number, year, object, place)
  5. Strong "what happened next" pull

If NONE of the 10 candidates satisfy rules 1-3, rewrite one of them yourself
to comply before returning.

Candidates:
{candidates}

Return JSON:
{{
  "final_title": string,           // <= 50 chars, no spoilers, one of T1-T5
  "first_frame_text": string,      // 4-6 word ALL-CAPS shock line for the
                                   //   on-screen text overlay in the first
                                   //   2 seconds of the video. Different from
                                   //   the title. Punchier, scarier, more
                                   //   visual. Example: "HE WOULDN'T DIE."
                                   //   or "9 BODIES. NO ANSWER."
  "description": string,            // 1-2 sentences, ends with 4-6 hashtags
                                   //   relevant to US history Shorts audience
                                   //   (#history #shorts #usa #didyouknow etc.)
  "tags": [string, ...]             // 10-15 YouTube tags
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
        temperature=0.85,
    )
    candidates: List[dict] = strat.get("candidates", [])
    eng = call_json(
        settings,
        ENGINEER_SYSTEM.format(niche=settings.niche),
        ENGINEER_USER.format(candidates=json.dumps(candidates, indent=2)),
        max_tokens=1500,
        temperature=0.4,
    )
    return {"candidates": candidates, **eng}
