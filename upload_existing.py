"""Upload an already-rendered short.mp4 using metadata from its run folder."""
import json
import sys
from pathlib import Path

from pipeline import upload
from pipeline.config import load_settings


def main(run_dir: Path) -> None:
    settings = load_settings()
    title_info = json.loads((run_dir / "title.json").read_text(encoding="utf-8"))
    video = run_dir / "short.mp4"
    if not video.exists():
        sys.exit(f"No short.mp4 in {run_dir}")
    url = upload.upload(
        settings,
        video,
        title_info["final_title"],
        title_info.get("description", title_info["final_title"]),
        title_info.get("tags", []),
    )
    print(f"Uploaded: {url}")
    (run_dir / "youtube_url.txt").write_text(url, encoding="utf-8")


if __name__ == "__main__":
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("workspace/20260419_180104")
    main(run)
