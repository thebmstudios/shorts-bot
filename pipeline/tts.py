"""ElevenLabs TTS: per-sentence synthesis with optional alternating voices,
accurate MP3 duration probing, and subtitle timing generation."""
from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import List

from elevenlabs.client import ElevenLabs

from .config import Settings


def _synth_one(client: ElevenLabs, voice_id: str, text: str, out_path: Path) -> Path:
    audio_iter = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id="eleven_multilingual_v2",
        text=text,
        output_format="mp3_44100_128",
        voice_settings={
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.15,
            "use_speaker_boost": True,
            "speed": 0.9,
        },
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        for chunk in audio_iter:
            if chunk:
                f.write(chunk)
    return out_path


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
        # Fallback heuristic
        return mp3_path.stat().st_size * 8 / 128000.0


# --- Public API ---


def synthesize_per_sentence(
    settings: Settings, sentences: List[str], out_dir: Path
) -> tuple[Path, list[dict]]:
    """Synthesize each sentence as its own MP3, alternating voices if secondary is set.
    Concatenates into `voice.mp3` and returns (final_mp3, cues_with_exact_timings).
    MP3 frames from same encoder/bitrate can be byte-concatenated safely.
    """
    client = ElevenLabs(api_key=settings.elevenlabs_api_key)
    voices = [settings.elevenlabs_voice_id]
    if settings.elevenlabs_voice_id_secondary:
        voices.append(settings.elevenlabs_voice_id_secondary)

    out_dir.mkdir(parents=True, exist_ok=True)
    parts_dir = out_dir / "parts"
    parts_dir.mkdir(exist_ok=True)

    cues: list[dict] = []
    cursor = 0.0
    combined = out_dir / "voice.mp3"
    with open(combined, "wb") as out_f:
        for idx, sentence in enumerate(sentences):
            voice = voices[idx % len(voices)]
            part_path = parts_dir / f"{idx:03d}.mp3"
            _synth_one(client, voice, sentence, part_path)
            dur = probe_duration_seconds(part_path)
            cues.append({
                "text": sentence,
                "start": round(cursor, 3),
                "end": round(cursor + dur, 3),
                "voice": voice,
            })
            cursor += dur
            out_f.write(part_path.read_bytes())
    return combined, cues


def write_subtitles_json(cues: list[dict], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(cues, indent=2), encoding="utf-8")
    return out_path
