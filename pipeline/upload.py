"""Upload rendered Shorts to YouTube via Data API v3 (OAuth desktop flow)."""
from __future__ import annotations

from pathlib import Path
from typing import List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .config import Settings

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


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


def upload(
    settings: Settings,
    video_path: Path,
    title: str,
    description: str,
    tags: List[str],
) -> str:
    creds = _get_credentials(settings)
    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags[:500],
            "categoryId": "22",  # People & Blogs; change to 27 (Education) if desired
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
    return f"https://youtube.com/shorts/{video_id}"
