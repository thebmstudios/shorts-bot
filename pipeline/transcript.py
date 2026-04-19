"""Fetch transcripts from YouTube Shorts/video URLs."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


@dataclass
class FetchedTranscript:
    video_id: str
    url: str
    text: str


def extract_video_id(url: str) -> str:
    """Handle youtu.be/<id>, youtube.com/watch?v=<id>, youtube.com/shorts/<id>."""
    url = url.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if "youtu.be" in host:
        return parsed.path.lstrip("/").split("/")[0]
    if "youtube.com" in host:
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/")[2]
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]
    raise ValueError(f"Cannot extract video id from URL: {url}")


_api = YouTubeTranscriptApi()


def fetch_transcript(url: str, languages: tuple[str, ...] = ("en", "en-US", "en-GB")) -> FetchedTranscript:
    vid = extract_video_id(url)
    try:
        fetched = _api.fetch(vid, languages=list(languages))
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as exc:
        raise RuntimeError(f"No transcript for {url}: {exc}") from exc
    parts = [snippet.text.replace("\n", " ").strip() for snippet in fetched if snippet.text]
    text = re.sub(r"\s+", " ", " ".join(parts)).strip()
    return FetchedTranscript(video_id=vid, url=url, text=text)


def fetch_many(urls: List[str]) -> List[FetchedTranscript]:
    results: List[FetchedTranscript] = []
    for u in urls:
        try:
            results.append(fetch_transcript(u))
        except Exception as exc:
            print(f"[transcript] skipped {u}: {exc}")
    if not results:
        raise RuntimeError("No transcripts could be fetched.")
    return results
