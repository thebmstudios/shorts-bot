"""Upload rendered Shorts to YouTube via Data API v3 (OAuth desktop flow).
Also uploads an English SRT caption track so YouTube auto-translates
into 50+ languages for global reach."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .config import Settings

# force-ssl covers upload + captions.insert
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def _get_credentials(settings: Settings) -> Credentials:
    creds: Credentials | None = None
    token_path = settings.youtube_token_path
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not settings.youtube_client_secret_path.exists():
                raise FileNotFoundError(
                    f"client_secret.json missing at {settings.youtube_client_secret_path}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(settings.youtube_client_secret_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _cues_to_srt(cues: list[dict]) -> str:
    """Convert [{start, end, text}, ...] to SRT format."""
    def fmt(t: float) -> str:
        hrs = int(t // 3600)
        mins = int((t % 3600) // 60)
        secs = int(t % 60)
        ms = int(round((t - int(t)) * 1000))
        if ms >= 1000:
            secs += 1
            ms = 0
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"

    lines: list[str] = []
    for i, cue in enumerate(cues, 1):
        start = float(cue.get("start", 0.0))
        end = float(cue.get("end", start + 1.0))
        text = str(cue.get("text", "")).strip()
        if not text:
            continue
        lines.append(str(i))
        lines.append(f"{fmt(start)} --> {fmt(end)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


_LANG_DISPLAY = {
    "en": "English",
    "tr": "Türkçe",
    "es": "Español",
    "de": "Deutsch",
    "fr": "Français",
    "ar": "العربية",
    "hi": "हिन्दी",
    "pt": "Português",
    "ru": "Русский",
    "ja": "日本語",
    "zh": "中文",
}


def _upload_caption(
    youtube, video_id: str, srt_content: str, lang: str = "en"
) -> None:
    """Attach an SRT track in the given language so YouTube auto-translates from it."""
    code = (lang or "en").lower()
    name = _LANG_DISPLAY.get(code, code.upper())
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".srt", delete=False, encoding="utf-8"
        )
        tmp.write(srt_content)
        tmp.close()
        media = MediaFileUpload(
            tmp.name, chunksize=-1, resumable=False, mimetype="application/octet-stream"
        )
        body = {
            "snippet": {
                "videoId": video_id,
                "language": code,
                "name": name,
                "isDraft": False,
            }
        }
        youtube.captions().insert(part="snippet", body=body, media_body=media).execute()
        print(f"[captions] {name} SRT uploaded (YouTube auto-translate enabled)")
    except Exception as e:
        print(f"[captions] warn: {name} caption upload failed (video still live): {e}")
    finally:
        if tmp is not None:
            try:
                Path(tmp.name).unlink(missing_ok=True)
            except Exception:
                pass


def upload(
    settings: Settings,
    video_path: Path,
    title: str,
    description: str,
    tags: List[str],
    cues: list[dict] | None = None,
    caption_lang: str = "en",
) -> str:
    creds = _get_credentials(settings)
    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags[:500],
            "categoryId": "22",  # People & Blogs; change to 27 (Education) if desired
            # Audio is always English (TTS voice). defaultLanguage reflects the
            # caption track's language so YouTube treats it as the source for
            # auto-translation into other languages.
            "defaultLanguage": (caption_lang or "en").lower(),
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": settings.youtube_privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = req.next_chunk()
        if status:
            print(f"[upload] progress {int(status.progress() * 100)}%")
    video_id = response["id"]

    # Upload SRT caption track (best-effort; doesn't block video URL return)
    if cues:
        srt = _cues_to_srt(cues)
        if srt.strip():
            _upload_caption(youtube, video_id, srt, lang=caption_lang)

    return f"https://youtube.com/shorts/{video_id}"
