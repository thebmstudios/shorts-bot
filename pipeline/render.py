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
    cmd = [
        npx,
        "remotion",
        "render",
        "src/index.ts",
        COMPOSITION_ID,
        str(out_mp4),
        f"--props={props_path}",
        "--overwrite",
    ]
    print(f"[render] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=settings.root, check=True, shell=False)
    return out_mp4
