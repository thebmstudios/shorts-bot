"""AI image generation via Hugging Face Inference API (FLUX.1-schnell).

Used as a fallback when Wikipedia returns too few topic-relevant images.
Style is conditioned on the topic category so each kind of story gets a
visually distinct look:
  history     -> sepia / painterly / dramatic chiaroscuro
  real-events -> documentary photography / high contrast / news still
  paranormal  -> cold blue / fog / eerie / cinematic dread

API:
  POST https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell
  Headers: Authorization: Bearer $HUGGINGFACE_API_KEY
  Body:    {"inputs": "<prompt>"}
  Returns: binary image bytes (PNG/JPEG)

Free tier: ~30k inference requests/month (HF). Plenty for 6 videos/day with
3-4 AI fallback images per video.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import httpx

# FLUX.1-schnell is fast (4 steps) and license-permissive. Quality is good
# enough for vertical short-form b-roll where motion + caption dominate.
# NOTE: HF retired api-inference.huggingface.co in 2025 — use router.* instead.
_HF_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"

# Style suffix appended to every prompt to enforce a consistent look per
# category. All include "no text, no watermark" because HF FLUX occasionally
# bakes letters into images, which look broken under our subtitle overlay.
_STYLE_BY_CATEGORY: dict[str, str] = {
    "history":     "cinematic painterly oil-painting style, dramatic chiaroscuro lighting, sepia and deep red tones, historical accuracy, vertical 9:16 composition, no text, no watermark, no modern objects",
    "real-events": "documentary photograph, high contrast realism, archival film grain, muted color, vertical 9:16 composition, no text, no watermark",
    "paranormal":  "cinematic eerie atmosphere, cold blue and cyan tones, low fog, dim moonlight, mysterious mood, vertical 9:16 composition, no text, no watermark",
}
_DEFAULT_STYLE = _STYLE_BY_CATEGORY["history"]


def build_prompt(subject: str, category: str = "") -> str:
    """Compose a FLUX prompt from the b-roll subject + category style."""
    subject = (subject or "").strip()
    cat = (category or "").strip().lower()
    style = _STYLE_BY_CATEGORY.get(cat, _DEFAULT_STYLE)
    if not subject:
        subject = "historical scene"
    return f"{subject}, {style}"


def generate_image(
    subject: str,
    out_path: Path,
    category: str = "",
    api_key: str | None = None,
    timeout_s: float = 60.0,
    retries: int = 2,
) -> Path | None:
    """Generate ONE image and save it to `out_path`. Returns the path on
    success, None on failure (caller decides whether to fall back further).

    Failure modes that return None silently:
      - HUGGINGFACE_API_KEY is not set (we just skip AI augmentation)
      - HF returns a 503 "model loading" several times in a row
      - Network error / timeout
      - Empty body
    """
    key = api_key or os.environ.get("HUGGINGFACE_API_KEY", "").strip()
    if not key:
        # Silent: it's a feature flag, not an error.
        return None
    prompt = build_prompt(subject, category)
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "image/png",
        "Content-Type": "application/json",
    }
    body = {"inputs": prompt}
    last_err: str = ""
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout_s) as client:
                r = client.post(_HF_URL, headers=headers, json=body)
            if r.status_code == 503:
                # FLUX cold-starts on free tier; HF asks us to wait.
                wait = min(20, 4 * (attempt + 1))
                print(f"[ai_image] HF model loading (503), retry in {wait}s")
                time.sleep(wait)
                continue
            if r.status_code != 200:
                last_err = f"HTTP {r.status_code}: {r.text[:140]}"
                break
            if not r.content or len(r.content) < 1024:
                last_err = "empty/tiny response body"
                break
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(r.content)
            print(f"[ai_image] generated '{subject[:50]}' -> {out_path.name}")
            return out_path
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt < retries:
                time.sleep(2.0 * (attempt + 1))
                continue
    print(f"[ai_image] FAIL '{subject[:60]}' ({last_err})")
    return None
