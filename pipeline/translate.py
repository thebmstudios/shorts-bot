"""Translate narration cues into another language while preserving timings.

Used when the upload target audience is non-English (e.g. Turkish prime-time
slots) — the audio stays English but the burnt-in subtitles and the YouTube
caption track are written in the target language.
"""
from __future__ import annotations

import json
from typing import Any

from .config import Settings
from .llm import call_json

# ISO code -> human language name passed to the LLM.
LANG_NAME = {
    "en": "English",
    "tr": "Turkish",
    "es": "Spanish",
    "de": "German",
    "fr": "French",
    "ar": "Arabic",
    "hi": "Hindi",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "zh": "Chinese (Simplified)",
}


def translate_sentences(
    settings: Settings, sentences: list[str], target_lang: str
) -> list[str]:
    """Translate sentences in order. Output length always equals input length.

    On any LLM hiccup we fall back to the original sentences so the pipeline
    never breaks because of a translation step."""
    if not sentences or target_lang.lower() in ("", "en"):
        return list(sentences)
    lang_name = LANG_NAME.get(target_lang.lower(), target_lang)
    system = (
        f"You are a professional subtitle translator into {lang_name}. "
        "Translate naturally for spoken-style YouTube Shorts subtitles — "
        "punchy, idiomatic, no literal word-for-word. "
        "Preserve proper nouns (names, places, dates) but transliterate / localize "
        "where natural in the target language. "
        "Output MUST be JSON only."
    )
    user = (
        f"Translate each of the following narration sentences into {lang_name}.\n"
        "RULES:\n"
        "- Output JSON: {{\"translations\": [string, ...]}} with the SAME length and ORDER as the input.\n"
        "- One translation per input index. No merges, no splits.\n"
        "- No explanations, no notes, no source-language echoes.\n\n"
        f"Input ({len(sentences)} sentences):\n"
        f"{json.dumps(sentences, ensure_ascii=False, indent=2)}"
    )
    try:
        result: Any = call_json(settings, system, user, max_tokens=2500, temperature=0.3)
        out = result.get("translations") if isinstance(result, dict) else None
        if not isinstance(out, list):
            raise ValueError("missing 'translations' array")
        # Force exact length: pad with originals or truncate.
        if len(out) < len(sentences):
            out = list(out) + sentences[len(out):]
        elif len(out) > len(sentences):
            out = out[: len(sentences)]
        # Coerce all to strings, fall back to original on empty.
        return [str(t).strip() or s for t, s in zip(out, sentences)]
    except Exception as e:
        print(f"[translate] failed ({e}); keeping English")
        return list(sentences)


def translate_cues(
    settings: Settings, cues: list[dict], target_lang: str
) -> list[dict]:
    """Return cues with .text translated; start/end timings unchanged."""
    if not cues or target_lang.lower() in ("", "en"):
        return cues
    sentences = [str(c.get("text", "")) for c in cues]
    translated = translate_sentences(settings, sentences, target_lang)
    return [{**c, "text": t} for c, t in zip(cues, translated)]
