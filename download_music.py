"""Download 7 curated royalty-free music tracks into assets/music/.

Source: incompetech.com (Kevin MacLeod), licensed CC-BY 4.0.
The bot auto-includes the required attribution in every video description.

Usage:
    python download_music.py
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "assets" / "music"

# (target filename, source URL, vibe label)
TRACKS = [
    ("01_suspense.mp3",
     "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Long%20Note%20Three.mp3",
     "suspenseful drone (real-events)"),
    ("02_dark_doc.mp3",
     "https://incompetech.com/music/royalty-free/mp3-royaltyfree/The%20Dread.mp3",
     "dark dramatic (history)"),
    ("03_historical.mp3",
     "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heart%20of%20the%20Beast.mp3",
     "epic historical (history)"),
    ("04_tension.mp3",
     "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Industrial%20Cinematic.mp3",
     "documentary tension (real-events)"),
    ("05_mystery.mp3",
     "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Crypto.mp3",
     "mystery cinematic (paranormal)"),
    ("06_epic.mp3",
     "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heavy%20Interlude.mp3",
     "heavy dramatic (history)"),
    ("07_paranormal.mp3",
     "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Hush.mp3",
     "eerie ambient (paranormal)"),
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[music] downloading {len(TRACKS)} tracks to {OUT_DIR}\n")
    ok = 0
    for filename, url, vibe in TRACKS:
        target = OUT_DIR / filename
        if target.exists() and target.stat().st_size > 50_000:
            print(f"  SKIP  {filename}  (already present, {target.stat().st_size:,} bytes)")
            ok += 1
            continue
        print(f"  GET   {filename}  ({vibe})", end=" ", flush=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            target.write_bytes(data)
            print(f"-> {len(data):,} bytes OK")
            ok += 1
        except Exception as e:
            print(f"FAIL ({e})")
    print(f"\n[music] done. {ok}/{len(TRACKS)} tracks ready in {OUT_DIR}")
    print("\nLicense: CC-BY 4.0 (Kevin MacLeod, incompetech.com).")
    print("The bot auto-includes the attribution in every video description.")


if __name__ == "__main__":
    main()
