"""Translate narration cues into another language while preserving timings.

Used when the upload target audience is non-English (e.g. Turkish prime-time
slots) — the audio stays English but the burnt-in subtitles and the YouTube
caption track are written in the target language.
"""
from __future__ import annotations

import json
from typing import Any

from .config import Settings
from .llm import MODEL_CHEAP, call_json

# ISO code -> human language name passed to the LLM.
LANG_NAME = {
    "en": "English",
    "tr": "Turkish",
    "es": "Spanish",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "ko": "Korean",
    "id": "Indonesian",
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
        result: Any = call_json(
            settings, system, user,
            max_tokens=2500, temperature=0.3,
            model=MODEL_CHEAP,  # translation is a low-stakes formulaic task
        )
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


def translate_sentences_multi(
    settings: Settings,
    sentences: list[str],
    target_langs: list[str],
) -> dict[str, list[str]]:
    """Translate one list of sentences into MANY languages in a SINGLE API call.

    Returns {lang_code: [translated_sentences]}. Each list has the same length
    as `sentences`. On any failure for a given language we fall back to the
    English originals so the pipeline never breaks.

    This is the cost-optimized path: instead of N separate Claude calls (one
    per language) we send a single prompt that asks for all languages at once.
    Combined with the Haiku model this brings the per-video translation cost
    down ~10x vs the old sequential-Sonnet setup.
    """
    out: dict[str, list[str]] = {}
    if not sentences:
        return out
    # Filter out empty / English (English is the source, no need to translate).
    targets = [l.strip().lower() for l in target_langs if l and l.strip().lower() not in ("", "en")]
    if not targets:
        return out

    lang_names = {l: LANG_NAME.get(l, l) for l in targets}
    system = (
        "You are a professional subtitle translator. You translate one English "
        "narration into multiple languages at once, for spoken-style YouTube "
        "Shorts subtitles. Translations must be punchy, idiomatic, NOT literal. "
        "Preserve proper nouns; transliterate / localize where natural. "
        "Output MUST be JSON only — no markdown, no commentary."
    )
    user = (
        f"Translate the following {len(sentences)} English narration sentences "
        f"into ALL of these languages: {', '.join(lang_names.values())}.\n\n"
        "Return JSON with this EXACT schema:\n"
        "{\n"
        + ",\n".join(
            f'  "{code}": [string, ...]  // {len(sentences)} translations in {name}, same order'
            for code, name in lang_names.items()
        )
        + "\n}\n\n"
        "RULES:\n"
        f"- Every language array MUST have EXACTLY {len(sentences)} items (same order as input).\n"
        "- No merges, no splits.\n"
        "- No explanations, no notes, no source-language echoes.\n"
        f"- Keep each translation length close to the original (subtitle-friendly).\n\n"
        f"Input sentences:\n{json.dumps(sentences, ensure_ascii=False, indent=2)}"
    )
    try:
        # Generous max_tokens because we're producing N langs × M sentences in one
        # response. Roughly: each sentence ~30-60 tokens output × langs.
        result: Any = call_json(
            settings, system, user,
            max_tokens=4000, temperature=0.3,
            model=MODEL_CHEAP,
        )
        if not isinstance(result, dict):
            raise ValueError("expected JSON object")
        for code in targets:
            translated = result.get(code)
            if not isinstance(translated, list) or not translated:
                print(f"[translate-multi] missing/empty for {code}; keeping English")
                out[code] = list(sentences)
                continue
            # Force exact length.
            if len(translated) < len(sentences):
                translated = list(translated) + sentences[len(translated):]
            elif len(translated) > len(sentences):
                translated = translated[: len(sentences)]
            out[code] = [str(t).strip() or s for t, s in zip(translated, sentences)]
    except Exception as e:
        print(f"[translate-multi] batch call failed ({e}); falling back per-lang")
        # Fallback to old per-lang path so caller still gets something.
        for code in targets:
            out[code] = translate_sentences(settings, sentences, code)
    return out


def translate_cues_multi(
    settings: Settings, cues: list[dict], target_langs: list[str]
) -> dict[str, list[dict]]:
    """Same as translate_sentences_multi but returns dicts of cues with timing."""
    if not cues:
        return {}
    sentences = [str(c.get("text", "")) for c in cues]
    per_lang = translate_sentences_multi(settings, sentences, target_langs)
    return {
        lang: [{**c, "text": t} for c, t in zip(cues, translated)]
        for lang, translated in per_lang.items()
    }
