"""End-to-end YouTube Shorts pipeline.

Usage:
    python main.py --urls https://youtube.com/shorts/XXX https://youtube.com/shorts/YYY
    python main.py --urls-file urls.txt
    python main.py --urls-file urls.txt --skip-upload
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from pipeline import (
    analyzer,
    titles,
    topic as topic_mod,
    translate,
    tts,
    render,
    upload,
    visuals,
    writer,
)
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
    try:
        transcripts = fetch_many(urls)
        (run_dir / "transcripts.json").write_text(
            json.dumps([t.__dict__ for t in transcripts], indent=2), encoding="utf-8"
        )
        print("[2/7] Forensic analysis...")
        findings = analyzer.analyze(settings, transcripts)
    except Exception as exc:
        print(f"[transcript] fetch failed ({exc}); using pipeline/default_findings.json")
        default_path = Path(__file__).parent / "pipeline" / "default_findings.json"
        findings = json.loads(default_path.read_text(encoding="utf-8"))
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
    story_arc = str(chosen_topic.get("story_arc", "")).strip() or "hidden-truth"
    script = writer.write_script(settings, final_title, findings, story_arc=story_arc)
    (run_dir / "script.json").write_text(json.dumps(script, indent=2), encoding="utf-8")

    print("[6/8] Synthesizing voice + subtitles...")
    voice_path, cues = tts.synthesize_per_sentence(settings, script["sentences"], run_dir)
    duration = cues[-1]["end"] if cues else 0.0
    print(f"   voice duration ~{duration:.1f}s, {len(cues)} cues")

    # Optional subtitle translation. Audio stays English; only the on-screen
    # subtitles and the YouTube caption track switch to the target language.
    sub_lang = os.environ.get("SUBTITLE_LANG", "en").strip().lower() or "en"
    if sub_lang != "en" and cues:
        print(f"[6b/8] Translating subtitles -> {sub_lang}...")
        cues = translate.translate_cues(settings, cues, sub_lang)
    tts.write_subtitles_json(cues, run_dir / "subtitles.json")

    print("[7/8] Fetching topic visuals from Wikipedia...")
    keywords = script.get("b_roll_keywords") or []
    # The LLM sometimes returns verbose multi-clause topics. Strip to the headline
    # phrase (before the first colon, capped at 6 words) so it's a real Wikipedia query.
    raw_topic = chosen_topic["topic"]
    short_topic = raw_topic.split(":", 1)[0].strip()
    short_topic = " ".join(short_topic.split()[:6])
    # Prepend short topic so the first image is the strongest on-topic anchor.
    keywords = [short_topic] + keywords
    images = visuals.fetch_images(
        keywords,
        run_dir / "images",
        min_count=6,
        topic_context=short_topic,
    )
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
    url = upload.upload(
        settings,
        out_mp4,
        final_title,
        description,
        tags,
        cues=cues,
        caption_lang=sub_lang,
    )
    print(f"[done] {url}")
    (run_dir / "youtube_url.txt").write_text(url, encoding="utf-8")
    # Persist topic + pool/format so future runs can enforce diversity rules.
    try:
        topic_mod.append_topic_to_history(settings.root, chosen_topic["topic"])
        topic_mod.append_topic_metadata(
            settings.root,
            chosen_topic["topic"],
            pool=str(chosen_topic.get("pool", "")).strip() or topic_mod._infer_pool(chosen_topic["topic"]),
            fmt=str(chosen_topic.get("format", "")).strip(),
            category=str(chosen_topic.get("category", "")).strip(),
            story_arc=str(chosen_topic.get("story_arc", "")).strip(),
        )
        print(f"[history] appended topic + metadata")
    except Exception as e:
        print(f"[history] warn: could not append topic history: {e}")


if __name__ == "__main__":
    main()
