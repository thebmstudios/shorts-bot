"""Trigger Remotion render via npx."""
from __future__ import annotations

import json
import random
import shutil
import subprocess
from pathlib import Path

from .config import Settings

COMPOSITION_ID = "Shorts"

# Map content category -> list of music filenames in assets/music/.
# Each category has 2-3 tracks; one is picked at random per render for variety.
# Filenames must match what the user dropped into assets/music/.
MUSIC_BY_CATEGORY: dict[str, list[str]] = {
    "history":     ["02_dark_doc.mp3", "03_historical.mp3", "06_epic.mp3"],
    "real-events": ["01_suspense.mp3", "04_tension.mp3"],
    "paranormal":  ["05_mystery.mp3", "07_paranormal.mp3"],
}


def _pick_music(category: str, music_dir: Path) -> str | None:
    """Return the basename (e.g. '02_dark_doc.mp3') of a music track to play
    underneath the voiceover. Returns None if no music file is available — in
    that case the render simply skips music (back-compat with old setups).
    """
    cat = (category or "").strip().lower()
    candidates = MUSIC_BY_CATEGORY.get(cat, [])
    # Fall back: if the requested category has no tracks present, try ANY
    # track that exists (so the first install with one track still gets music).
    if not candidates:
        candidates = [p.name for p in music_dir.glob("*.mp3")]
    available = [name for name in candidates if (music_dir / name).is_file()]
    if not available:
        return None
    return random.choice(available)


def render(
    settings: Settings,
    subtitles_cues: list[dict],
    voice_mp3: Path,
    out_mp4: Path,
    duration_seconds: float,
    image_rels: list[str] | None = None,
    category: str = "",
) -> Path:
    """Copy assets into /public and invoke remotion render.

    If a music track matching the topic's category exists under
    assets/music/, it is staged into /public/ and passed to Remotion as
    `musicSrc`. The composition mixes it under the voiceover with fade
    in/out. Missing music = silent render (back-compat).
    """
    public = settings.public_dir
    public.mkdir(exist_ok=True)

    voice_target = public / "voice.mp3"
    shutil.copyfile(voice_mp3, voice_target)

    subs_target = public / "subtitles.json"
    subs_target.write_text(json.dumps(subtitles_cues, indent=2), encoding="utf-8")

    # --- Stage background music if one is available for this category ---
    music_dir = settings.root / "assets" / "music"
    music_name = _pick_music(category, music_dir) if music_dir.exists() else None
    music_rel: str | None = None
    if music_name:
        music_target = public / "music.mp3"
        shutil.copyfile(music_dir / music_name, music_target)
        music_rel = "music.mp3"
        print(f"[render] music: {music_name} (category={category or 'n/a'})")
    else:
        print(f"[render] music: none (no track for category={category or 'n/a'})")

    props = {
        "durationSeconds": duration_seconds,
        "voiceSrc": "voice.mp3",
        "subtitlesSrc": "subtitles.json",
        "images": image_rels or [],
        "musicSrc": music_rel,
    }
    props_path = settings.workspace_dir / "props.json"
    props_path.write_text(json.dumps(props), encoding="utf-8")

    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    npx = shutil.which("npx") or "npx"
    # Speed flags:
    #   --concurrency=100% : use every CPU core the runner has (GH free 2-core
    #                        runners default to single-threaded otherwise).
    #   --jpeg-quality=80  : slightly faster frame extraction (visually lossless
    #                        for short-form vertical video).
    #   --crf=26           : ~30% faster H.264 encode vs Remotion's default 18.
    #                        At 1080x1920 this is still YouTube-safe quality.
    #   --x264-preset=fast : ffmpeg encoder preset, cuts encode time ~40% vs
    #                        the default "medium".
    cmd = [
        npx,
        "remotion",
        "render",
        "src/index.ts",
        COMPOSITION_ID,
        str(out_mp4),
        f"--props={props_path}",
        "--overwrite",
        "--concurrency=100%",
        "--jpeg-quality=80",
        "--crf=26",
        "--x264-preset=fast",
    ]
    print(f"[render] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=settings.root, check=True, shell=False)
    return out_mp4
