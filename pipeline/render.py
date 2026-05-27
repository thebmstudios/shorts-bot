"""Trigger Remotion render via npx."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .config import Settings

COMPOSITION_ID = "Shorts"


def render(
    settings: Settings,
    subtitles_cues: list[dict],
    voice_mp3: Path,
    out_mp4: Path,
    duration_seconds: float,
    image_rels: list[str] | None = None,
) -> Path:
    """Copy assets into /public and invoke remotion render."""
    public = settings.public_dir
    public.mkdir(exist_ok=True)

    voice_target = public / "voice.mp3"
    shutil.copyfile(voice_mp3, voice_target)

    subs_target = public / "subtitles.json"
    subs_target.write_text(json.dumps(subtitles_cues, indent=2), encoding="utf-8")

    props = {
        "durationSeconds": duration_seconds,
        "voiceSrc": "voice.mp3",
        "subtitlesSrc": "subtitles.json",
        "images": image_rels or [],
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
