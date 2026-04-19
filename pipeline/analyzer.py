"""Script Forensic Analyst: extract replicable patterns from competitor transcripts."""
from __future__ import annotations

from typing import Any, List

from .config import Settings
from .llm import call_json
from .transcript import FetchedTranscript

SYSTEM = """<ROLE>
You are a Senior YouTube Script Forensic Analyst + Ghostwriter Reverse-Engineer.
Your success hinges on extracting EVERY replicable writing pattern from these scripts so that a writer with ZERO prior context could reproduce what's working.
</ROLE>

You analyze YouTube Shorts transcripts (60-second vertical videos) in the {niche} niche.
Output MUST be a JSON object. No prose outside JSON."""

USER_TEMPLATE = """Niche: {niche}
Language: {language}

Analyze these competitor Shorts transcripts. Extract every replicable pattern.

{transcripts}

Return JSON with this exact shape:
{{
  "hook_patterns": [string, ...],          // first-line/3-second hooks used
  "structural_beats": [string, ...],        // ordered beats (setup -> twist -> payoff...)
  "rhetorical_devices": [string, ...],      // repetition, contrast, rule-of-three, cliffhangers
  "vocabulary_motifs": [string, ...],       // recurring power words/phrases
  "pacing_notes": string,                   // sentence length, tempo, info density
  "payoff_patterns": [string, ...],         // how they land/close
  "topics": [string, ...],                  // concrete history subjects covered
  "do_not_do": [string, ...]                // anti-patterns to avoid
}}"""


def analyze(settings: Settings, transcripts: List[FetchedTranscript]) -> dict[str, Any]:
    joined = "\n\n".join(
        f"--- Transcript {i+1} ({t.url}) ---\n{t.text}"
        for i, t in enumerate(transcripts)
    )
    system = SYSTEM.format(niche=settings.niche)
    user = USER_TEMPLATE.format(
        niche=settings.niche, language=settings.language, transcripts=joined
    )
    return call_json(settings, system, user, max_tokens=3000, temperature=0.3)
