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


def _tokens(s: str) -> set[str]:
    """Lowercase word tokens, length>=3, for relevance scoring."""
    return {w for w in "".join(c if c.isalnum() else " " for c in s.lower()).split() if len(w) >= 3}


def _score_page(page: dict, keyword: str, topic_context: str) -> float:
    """Higher = more relevant. Combines title overlap with keyword + topic + has-original-image."""
    title = page.get("title", "")
    title_toks = _tokens(title)
    kw_toks = _tokens(keyword)
    topic_toks = _tokens(topic_context) if topic_context else set()
    if not title_toks:
        return 0.0
    kw_overlap = len(title_toks & kw_toks) / max(len(kw_toks), 1)
    topic_overlap = len(title_toks & topic_toks) / max(len(topic_toks), 1) if topic_toks else 0.0
    # Wikipedia search gives `index` (lower = better hit). Convert to a small bonus.
    idx = page.get("index", 99)
    rank_bonus = max(0.0, 0.3 - 0.05 * idx)
    has_orig = 0.15 if page.get("original", {}).get("source") else 0.0
    # Heavy weight on direct keyword match; topic context is secondary safety net.
    return kw_overlap * 1.0 + topic_overlap * 0.4 + rank_bonus + has_orig


def _search_image(
    query: str, client: httpx.Client, topic_context: str = "", min_score: float = 0.15
) -> str | None:
    """Return best image URL for a search query, or None.

    Searches Wikipedia with the bare keyword (composing with the full topic over-
    constrains the query — verbose topics from the LLM choke the search), then
    re-ranks the top 5 candidates by title overlap with the keyword AND the
    topic context. Rejects results whose relevance score is below min_score."""
    params = {
        "action": "query",
        "format": "json",
        "prop": "pageimages",
        "piprop": "original|thumbnail",
        "pithumbsize": "1600",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": "5",
    }
    try:
        r = client.get(WIKI_API, params=params, headers=HEADERS, timeout=15.0)
        r.raise_for_status()
        pages = list(r.json().get("query", {}).get("pages", {}).values())
    except Exception as e:
        print(f"[visuals] wiki search failed for '{query}': {e}")
        return None
    if not pages:
        return None
    # Score every candidate, keep only those above the relevance floor.
    scored = sorted(
        ((_score_page(p, query, topic_context), p) for p in pages),
        key=lambda x: x[0],
        reverse=True,
    )
    best_score, best_page = scored[0]
    if best_score < min_score:
        print(
            f"[visuals] rejected low-relevance result for '{query}' "
            f"(top='{best_page.get('title','?')}' score={best_score:.2f})"
        )
        return None
    # Walk scored list to find the first with a usable image URL.
    for score, page in scored:
        if score < min_score:
            break
        url = page.get("original", {}).get("source") or page.get("thumbnail", {}).get("source")
        if url:
            print(f"[visuals] '{query}' -> '{page.get('title','?')}' (score={score:.2f})")
            return url
    return None


def _is_valid_image(path: Path) -> bool:
    """Verify the file starts with a real raster image signature Remotion can decode."""
    try:
        with open(path, "rb") as f:
            head = f.read(16)
    except Exception:
        return False
    if len(head) < 8:
        return False
    # JPEG
    if head[:3] == b"\xff\xd8\xff":
        return True
    # PNG
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    # WEBP: RIFF....WEBP
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return True
    # GIF
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return True
    return False


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
            if not _is_valid_image(out_path):
                print(f"[visuals] rejected non-decodable image: {url}")
                try:
                    out_path.unlink()
                except Exception:
                    pass
                return None
            return out_path
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.5)
                continue
            print(f"[visuals] download failed {url}: {e}")
            return None
    return None


def fetch_images(
    keywords: List[str],
    out_dir: Path,
    min_count: int = 6,
    topic_context: str = "",
) -> List[Path]:
    """Fetch one image per keyword. Skips duplicates; tries to reach min_count.

    `topic_context` is the overall topic (e.g. "Suleiman the Magnificent siege of Vienna")
    used to bias and re-rank Wikipedia results so generic keywords still pull on-topic pages.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    seen: set[str] = set()
    # LLM can emit verbose multi-clause topics ("Julia Maesa (218-224 AD): The Syrian
    # powerbroker who..."). Trim to the first 8 words for scoring — keeps the proper
    # nouns without flooding the overlap math with stopwords.
    short_ctx = " ".join(topic_context.split()[:8]) if topic_context else ""
    with httpx.Client() as client:
        for kw in keywords:
            # If the keyword IS the topic, don't double-count it in scoring.
            ctx = "" if kw.strip().lower() == topic_context.strip().lower() else short_ctx
            url = _search_image(kw, client, topic_context=ctx)
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
