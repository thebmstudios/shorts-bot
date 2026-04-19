"""Load environment variables and expose settings."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: str
    elevenlabs_voice_id_secondary: str
    niche: str
    language: str
    target_views: int
    youtube_client_secret_path: Path
    youtube_token_path: Path
    youtube_privacy: str
    root: Path
    public_dir: Path
    workspace_dir: Path


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def load_settings() -> Settings:
    workspace = ROOT / "workspace"
    workspace.mkdir(exist_ok=True)
    return Settings(
        anthropic_api_key=_require("ANTHROPIC_API_KEY"),
        elevenlabs_api_key=_require("ELEVENLABS_API_KEY"),
        elevenlabs_voice_id=_require("ELEVENLABS_VOICE_ID"),
        elevenlabs_voice_id_secondary=os.environ.get("ELEVENLABS_VOICE_ID_SECONDARY", "").strip(),
        niche=os.environ.get("NICHE", "history"),
        language=os.environ.get("LANGUAGE", "English"),
        target_views=int(os.environ.get("TARGET_VIEWS", "1000000")),
        youtube_client_secret_path=ROOT / os.environ.get("YOUTUBE_CLIENT_SECRET_PATH", "client_secret.json"),
        youtube_token_path=ROOT / os.environ.get("YOUTUBE_TOKEN_PATH", "token.json"),
        youtube_privacy=os.environ.get("YOUTUBE_PRIVACY", "private"),
        root=ROOT,
        public_dir=ROOT / "public",
        workspace_dir=workspace,
    )
