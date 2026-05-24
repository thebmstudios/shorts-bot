"""Generate MP3 previews of candidate Edge TTS voices.

Plays the same short history-style sample for each voice so you can pick.
Outputs files to ./voice_previews/ — open them with any media player.

Usage:
    python preview_voices.py
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts

# Same hook line your bot would actually produce — picks the most
# storytelling-relevant phrasing so you hear the voice the way viewers will.
SAMPLE = (
    "Nine climbers. One night. Still no answer. "
    "In 1959, the Dyatlov Pass expedition vanished into the Ural mountains. "
    "What investigators found made them seal the file for thirty years."
)

VOICES = [
    ("en-US-AndrewNeural",     "warm, conversational — documentary feel"),
    ("en-US-BrianNeural",      "authoritative news-anchor — classic history"),
    ("en-US-DavisNeural",      "casual storyteller — close, intimate"),
    ("en-US-RogerNeural",      "mature documentary — Nat Geo style"),
    ("en-US-EricNeural",       "clear professional — least 'AI' sounding"),
    ("en-GB-RyanNeural",       "dramatic British — perfect for history"),
    ("en-GB-ThomasNeural",     "calm British storyteller"),
    ("en-US-ChristopherNeural","CURRENT voice — for comparison"),
]

OUT_DIR = Path(__file__).resolve().parent / "voice_previews"


async def render_one(voice: str, desc: str) -> bool:
    out = OUT_DIR / f"{voice}.mp3"
    print(f"  rendering {voice}  ({desc})", end=" ", flush=True)
    try:
        communicate = edge_tts.Communicate(SAMPLE, voice, rate="+0%")
        await communicate.save(str(out))
        print("OK")
        return True
    except Exception as e:
        print(f"SKIP ({type(e).__name__})")
        return False


async def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    print(f"[preview] writing {len(VOICES)} samples to {OUT_DIR}\n")
    ok = 0
    for voice, desc in VOICES:
        if await render_one(voice, desc):
            ok += 1
    print(f"\n[preview] done. {ok}/{len(VOICES)} voices rendered. Open the folder:\n  {OUT_DIR}")
    print("Play each .mp3 file and pick your favorite.")


if __name__ == "__main__":
    asyncio.run(main())
