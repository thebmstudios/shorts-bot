"""Edge TTS: per-sentence synthesis with accurate MP3 duration probing
and subtitle timing generation. Uses Microsoft Edge's free neural voices."""
from __future__ import annotations

import asyncio
import json
import struct
from pathlib import Path
from typing import List

import edge_tts

from .config import Settings


async def _synth_one_async(
    voice: str, rate: str, text: str, out_path: Path
) -> list[dict]:
    """Synthesize one sentence AND capture per-word timing for karaoke subs.

    Returns a list of {"text": "Word", "offset": float_sec_from_sentence_start,
    "duration": float_sec}. If the Edge TTS server skips WordBoundary events
    (rare), returns []; the caller will fall back to even-distribution timing.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    words: list[dict] = []
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            ct = chunk.get("type")
            if ct == "audio":
                f.write(chunk["data"])
            elif ct == "WordBoundary":
                # Edge sends offset/duration in 100-ns ticks.
                words.append({
                    "text": str(chunk.get("text", "")),
                    "offset": chunk["offset"] / 10_000_000,
                    "duration": chunk["duration"] / 10_000_000,
                })
    return words


def _synth_one(voice: str, rate: str, text: str, out_path: Path) -> list[dict]:
    return asyncio.run(_synth_one_async(voice, rate, text, out_path))


# --- MP3 duration probe (no external ffmpeg) ---

_MPEG_BITRATES = {
    1: [None, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448],  # V1 L1
    2: [None, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],     # V1 L2
    3: [None, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],      # V1 L3 (MP3)
    4: [None, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],     # V2 L1
    5: [None, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],          # V2 L2/L3
}
_MPEG_SAMPLE_RATES = {
    3: [44100, 48000, 32000],  # MPEG 1
    2: [22050, 24000, 16000],  # MPEG 2
    0: [11025, 12000, 8000],   # MPEG 2.5
}


def _mp3_duration(path: Path) -> float:
    """Decode MP3 frames to sum exact duration. Handles ID3v2 tag."""
    data = path.read_bytes()
    i = 0
    # Skip ID3v2
    if data[:3] == b"ID3":
        size = data[6] << 21 | data[7] << 14 | data[8] << 7 | data[9]
        i = 10 + size
    total = 0.0
    while i + 4 <= len(data):
        if data[i] != 0xFF or (data[i + 1] & 0xE0) != 0xE0:
            i += 1
            continue
        header = struct.unpack(">I", data[i:i + 4])[0]
        version_bits = (header >> 19) & 0x3
        layer_bits = (header >> 17) & 0x3
        bitrate_idx = (header >> 12) & 0xF
        samplerate_idx = (header >> 10) & 0x3
        padding = (header >> 9) & 0x1

        if version_bits == 1 or layer_bits == 0 or bitrate_idx == 0 or bitrate_idx == 15 or samplerate_idx == 3:
            i += 1
            continue

        # Pick tables
        if version_bits == 3 and layer_bits == 3:
            bitrates = _MPEG_BITRATES[3]; samples = 1152
        elif version_bits == 3 and layer_bits == 2:
            bitrates = _MPEG_BITRATES[2]; samples = 1152
        elif version_bits == 3 and layer_bits == 1:
            bitrates = _MPEG_BITRATES[1]; samples = 384
        elif layer_bits == 1:
            bitrates = _MPEG_BITRATES[5]; samples = 576
        elif layer_bits == 2:
            bitrates = _MPEG_BITRATES[5]; samples = 1152
        elif layer_bits == 3:
            bitrates = _MPEG_BITRATES[4]; samples = 384
        else:
            i += 1
            continue

        bitrate = bitrates[bitrate_idx]
        sr = _MPEG_SAMPLE_RATES[version_bits][samplerate_idx]
        if bitrate is None or sr is None:
            i += 1
            continue
        frame_len = int((samples // 8) * bitrate * 1000 // sr) + padding
        if frame_len <= 0:
            i += 1
            continue
        total += samples / sr
        i += frame_len
    return total


def probe_duration_seconds(mp3_path: Path) -> float:
    try:
        return _mp3_duration(mp3_path)
    except Exception:
        # Fallback heuristic (edge-tts uses 24kHz mono, ~48kbps)
        return mp3_path.stat().st_size * 8 / 48000.0


# --- Public API ---


def pick_voice_for_category(category: str, default: str) -> str:
    """Map content category -> Edge TTS voice.

    - history     -> en-US-BrianNeural   (authoritative, dramatic — fits
                                          emperors, battles, classical history)
    - real-events -> en-US-AndrewNeural  (warm conversational — true crime,
                                          cover-ups, survivals)
    - paranormal  -> en-US-AndrewNeural  (intimate storyteller — best for
                                          unease and "documented case" tone)

    Falls back to `default` (the env-configured voice) if category is unknown.
    """
    cat = (category or "").strip().lower()
    mapping = {
        "history":     "en-US-BrianNeural",
        "real-events": "en-US-AndrewNeural",
        "paranormal":  "en-US-AndrewNeural",
    }
    return mapping.get(cat, default)


def synthesize_per_sentence(
    settings: Settings,
    sentences: List[str],
    out_dir: Path,
    voice_override: str | None = None,
) -> tuple[Path, list[dict]]:
    """Synthesize each sentence as its own MP3 with Edge TTS.
    Concatenates into `voice.mp3` and returns (final_mp3, cues_with_exact_timings).
    MP3 frames from same encoder/bitrate can be byte-concatenated safely.

    If `voice_override` is provided, it wins over settings.tts_voice — this is
    how category-based voice routing in main.py reaches the synthesizer.
    """
    voice = voice_override or settings.tts_voice
    rate = settings.tts_rate

    out_dir.mkdir(parents=True, exist_ok=True)
    parts_dir = out_dir / "parts"
    parts_dir.mkdir(exist_ok=True)

    cues: list[dict] = []
    cursor = 0.0
    combined = out_dir / "voice.mp3"
    with open(combined, "wb") as out_f:
        for idx, sentence in enumerate(sentences):
            part_path = parts_dir / f"{idx:03d}.mp3"
            sentence_words = _synth_one(voice, rate, sentence, part_path)
            dur = probe_duration_seconds(part_path)
            # Convert per-sentence word offsets -> absolute timeline offsets
            # (offset from start of voice.mp3). If WordBoundary stream was
            # empty (Edge rare-skip case), fabricate even-distribution timing
            # so the karaoke effect still works.
            words_abs: list[dict] = []
            if sentence_words:
                for w in sentence_words:
                    words_abs.append({
                        "text": w["text"],
                        "start": round(cursor + w["offset"], 3),
                        "end": round(cursor + w["offset"] + w["duration"], 3),
                    })
            else:
                tokens = sentence.split()
                if tokens:
                    per = dur / len(tokens)
                    for i, tok in enumerate(tokens):
                        words_abs.append({
                            "text": tok,
                            "start": round(cursor + i * per, 3),
                            "end": round(cursor + (i + 1) * per, 3),
                        })
            cues.append({
                "text": sentence,
                "start": round(cursor, 3),
                "end": round(cursor + dur, 3),
                "voice": voice,
                "words": words_abs,
            })
            cursor += dur
            out_f.write(part_path.read_bytes())
    return combined, cues


def write_subtitles_json(cues: list[dict], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(cues, indent=2), encoding="utf-8")
    return out_path
