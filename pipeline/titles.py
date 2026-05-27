"""Title generator: single-call strategist + engineer.

Earlier this module made TWO Claude calls (one to brainstorm 10 candidates,
one to pick the best). Both passes are now fused into a single prompt that
internally drafts 10 candidates and then commits to one — same output schema,
~50% fewer tokens.

US-audience Shorts optimization (unchanged):
  - Under 50 characters
  - NO outcome words (died, killed, won, escaped, survived, executed)
  - One of 5 approved templates (pronoun-mystery / number+gap /
    negation hook / year+stake / question hook)
  - Title hints, video reveals.
"""
from __future__ import annotations

import json
from typing import Any

from .config import Settings
from .llm import call_json

SYSTEM = """<ROLE>
You are an Elite YouTube Shorts Title Strategist + Engineer for a US audience.
You internally brainstorm 10 candidates, then commit to the single best one,
in ONE response. You NEVER let a title resolve the story — spoilers in titles
are the #1 reason Shorts under-perform.
</ROLE>
Output MUST be JSON only — no markdown, no commentary."""

USER = """Niche: {niche}
Language: {language}
Audience: United States (Eastern Time mainstream)
Target views: {target_views}+

Chosen topic for our new Short:
{topic}

Forensic findings (style only — do NOT copy outcomes into the title):
{findings}

STEP 1 — DRAFT 10 CANDIDATES (you MUST output all 10 in the "candidates" array).
Each candidate uses ONE of these 5 templates (label which template):

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

DIVERSITY RULE: at least 4 of the 5 templates MUST be represented across the
10 candidates. No more than 3 candidates from the same template.

HARD BANS (any candidate that violates these is rejected before selection):
- Contains: died, killed, won, escaped, survived, executed, beheaded, murdered,
  slaughtered, conquered, destroyed, defeated.
- States the outcome (e.g. "Sultan Killed 7 Doctors Then Died From The 8th"
  is BANNED — spoils the entire story).
- Gives the famous person's full name AND their famous deed in the same line.
- Over 50 characters.
- All caps (Title Case only).
- Emojis.

CURIOSITY RULES:
- Read the title — can you predict the ending? If yes, it's a spoiler. Rewrite.
- Lead with pronoun, number, negation, year, or question word. Never lead with
  a famous person's name unless they're obscure enough that the name itself
  is the hook.
- Include one specific concrete detail (a number, an object, a year, a place)
  that the reader cannot place without watching.

STEP 2 — PICK THE BEST CANDIDATE for a US Shorts audience.

Selection priority (in order):
  1. No spoiler (cannot predict ending from title)
  2. Under 50 characters
  3. Uses an approved template (T1-T5)
  4. Specific concrete detail (number, year, object, place)
  5. Strong "what happened next" pull

If NONE of your 10 candidates satisfy rules 1-3, rewrite one of them yourself
to comply before committing. Do not return a non-compliant final_title.

STEP 3 — produce the on-screen first-frame text + description + tags.

Return JSON with this EXACT schema:
{{
  "candidates": [
    {{"title": string, "template": "T1"|"T2"|"T3"|"T4"|"T5", "curiosity_question": string}},
    ... 10 total
  ],
  "final_title": string,           // <= 50 chars, no spoilers, one of T1-T5
  "first_frame_text": string,      // 4-6 word ALL-CAPS shock line for the
                                   //   on-screen text overlay in the first
                                   //   2 seconds of the video. Different
                                   //   from the title — punchier, scarier,
                                   //   more visual. Example: "HE WOULDN'T DIE."
                                   //   or "9 BODIES. NO ANSWER."
  "description": string,           // 1-2 sentences, ends with 4-6 hashtags
                                   //   relevant to US history Shorts audience
                                   //   (#history #shorts #usa #didyouknow etc.)
  "tags": [string, ...]            // 10-15 YouTube tags
}}"""


def generate(settings: Settings, findings: dict[str, Any], topic: str) -> dict[str, Any]:
    return call_json(
        settings,
        SYSTEM.format(niche=settings.niche),
        USER.format(
            niche=settings.niche,
            language=settings.language,
            target_views=settings.target_views,
            findings=json.dumps(findings, indent=2),
            topic=topic,
        ),
        # max_tokens raised modestly to fit candidates[] + selection JSON
        # in one response (the old two-call setup used 2000 + 1500).
        max_tokens=2800,
        temperature=0.75,
    )
