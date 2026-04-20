"""Fetch topic-relevant images from Wikipedia (free, no API key)."""
from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path
from typing import List

import httpx

WIKI_API = "https://en.wikipedia.org/w/api.php"
# Wikipedia User-Agent policy: https://meta.wikimedia.org/wiki/User-Agent_policy
# Requires tool name, contact URL/email, and version. Generic UAs are blocked on cloud IPs.
HEADERS = {
    "User-Agent": (
        "ShortsBot/1.0 "
        "(https://github.com/thebmstudios/shorts-bot; muratsimsak1967@gmail.com) "
        "httpx/0.27"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


def _search_image(query: str, client: httpx.Client) -> str | None:
    """Return best image URL for a search query, or None."""
    params = {
        "action": "query",
        "format": "json",
        "prop": "pageimages",
        "piprop": "original|thumbnail",
        "pithumbsize": "1600",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": "3",
    }
    try:
        r = client.get(WIKI_API, params=params, headers=HEADERS, timeout=15.0)
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
    except Exception as e:
        print(f"[visuals] wiki search failed for '{query}': {e}")
        return None
    # Prefer original resolution, fall back to thumbnail
    for page in pages.values():
        orig = page.get("original", {}).get("source")
        if orig:
            return orig
    for page in pages.values():
        thumb = page.get("thumbnail", {}).get("source")
        if thumb:
            return thumb
    return None


def _download(url: str, out_path: Path, client: httpx.Client, retries: int = 3) -> Path | None:
    for attempt in range(retries):
        try:
            with client.stream("GET", url, headers=HEADERS, timeout=30.0, follow_redirects=True) as r:
                if r.status_code == 429:
                    wait = 2 ** attempt
                    print(f"[visuals] 429 rate-limited; retrying in {wait}s")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
            return out_path
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.5)
                continue
            print(f"[visuals] download failed {url}: {e}")
            return None
    return None


def fetch_images(keywords: List[str], out_dir: Path, min_count: int = 6) -> List[Path]:
    """Fetch one image per keyword. Skips duplicates; tries to reach min_count."""
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    seen: set[str] = set()
    with httpx.Client() as client:
        for kw in keywords:
            url = _search_image(kw, client)
            if not url or url in seen:
                continue
            seen.add(url)
            ext = ".jpg"
            low = url.lower()
            for candidate in (".png", ".webp", ".jpeg", ".jpg", ".svg"):
                if candidate in low:
                    ext = candidate if candidate != ".jpeg" else ".jpg"
                    break
            if ext == ".svg":
                continue  # skip vector — renderer won't treat it as photo
            name = hashlib.md5(url.encode()).hexdigest()[:10] + ext
            path = out_dir / name
            if _download(url, path, client):
                saved.append(path)
                if len(saved) >= max(min_count, 10):
                    break
            time.sleep(0.8)  # be polite to Wikimedia
    return saved


def copy_to_public(images: List[Path], public_dir: Path) -> list[str]:
    """Copy fetched images into /public/images/ and return relative filenames."""
    target = public_dir / "images"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    rels: list[str] = []
    for p in images:
        dest = target / p.name
        shutil.copyfile(p, dest)
        rels.append(f"images/{p.name}")
    return rels
