"""End-to-end YouTube Shorts pipeline.

Usage:
    python main.py --urls https://youtube.com/shorts/XXX https://youtube.com/shorts/YYY
    python main.py --urls-file urls.txt
    python main.py --urls-file urls.txt --skip-upload
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from pipeline import analyzer, titles, topic as topic_mod, tts, render, upload, visuals, writer
from pipeline.config import load_settings
from pipeline.transcript import fetch_many


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--urls", nargs="*", default=[], help="Competitor Shorts URLs")
    p.add_argument("--urls-file", type=Path, help="File with one URL per line")
    p.add_argument("--topic", help="Override topic (skips topic auto-selection)")
    p.add_argument("--skip-upload", action="store_true")
    p.add_argument("--skip-render", action="store_true")
    return p.parse_args()


def load_urls(args: argparse.Namespace) -> list[str]:
    urls = list(args.urls)
    if args.urls_file:
        urls.extend(
            line.strip()
            for line in args.urls_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        )
    if not urls:
        sys.exit("Provide --urls or --urls-file")
    return urls


def main() -> None:
    args = parse_args()
    settings = load_settings()
    urls = load_urls(args)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = settings.workspace_dir / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/7] Fetching {len(urls)} transcripts...")
    transcripts = fetch_many(urls)
    (run_dir / "transcripts.json").write_text(
        json.dumps([t.__dict__ for t in transcripts], indent=2), encoding="utf-8"
    )

    print("[2/7] Forensic analysis...")
    findings = analyzer.analyze(settings, transcripts)
    (run_dir / "findings.json").write_text(json.dumps(findings, indent=2), encoding="utf-8")

    if args.topic:
        chosen_topic = {"topic": args.topic, "angle": "", "why": "user-provided"}
    else:
        print("[3/7] Choosing topic...")
        chosen_topic = topic_mod.choose_topic(settings, findings)
    (run_dir / "topic.json").write_text(json.dumps(chosen_topic, indent=2), encoding="utf-8")
    print(f"   topic: {chosen_topic['topic']}")

    print("[4/7] Generating title...")
    title_info = titles.generate(settings, findings, chosen_topic["topic"])
    (run_dir / "title.json").write_text(json.dumps(title_info, indent=2), encoding="utf-8")
    final_title = title_info["final_title"]
    print(f"   title: {final_title}")

    print("[5/7] Writing script...")
    script = writer.write_script(settings, final_title, findings)
    (run_dir / "script.json").write_text(json.dumps(script, indent=2), encoding="utf-8")

    print("[6/8] Synthesizing voice + subtitles...")
    voice_path, cues = tts.synthesize_per_sentence(settings, script["sentences"], run_dir)
    tts.write_subtitles_json(cues, run_dir / "subtitles.json")
    duration = cues[-1]["end"] if cues else 0.0
    print(f"   voice duration ~{duration:.1f}s, {len(cues)} cues")

    print("[7/8] Fetching topic visuals from Wikipedia...")
    keywords = script.get("b_roll_keywords") or []
    # also prepend topic name for stronger relevance
    keywords = [chosen_topic["topic"]] + keywords
    images = visuals.fetch_images(keywords, run_dir / "images", min_count=6)
    print(f"   fetched {len(images)} images")

    if args.skip_render:
        print("--skip-render set; exiting.")
        return

    print("[8/8] Rendering video...")
    out_mp4 = run_dir / "short.mp4"
    image_rels = visuals.copy_to_public(images, settings.public_dir)
    render.render(settings, cues, voice_path, out_mp4, duration, image_rels)
    print(f"   rendered: {out_mp4}")

    if args.skip_upload:
        print("--skip-upload set; exiting.")
        return

    print("[upload] Uploading to YouTube...")
    description = title_info.get("description", final_title)
    tags = title_info.get("tags", [])
    url = upload.upload(settings, out_mp4, final_title, description, tags)
    print(f"[done] {url}")
    (run_dir / "youtube_url.txt").write_text(url, encoding="utf-8")


if __name__ == "__main__":
    main()
