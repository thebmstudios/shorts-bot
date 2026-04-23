"""Pick a fresh topic based on forensic findings. Avoids repeating recent subjects."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Settings
from .llm import call_json

SYSTEM = """You are a content strategist for a {niche} Shorts channel.
You MUST avoid repeating subjects, figures, or events that appear in the "Recently covered" list.
Output MUST be JSON only."""

USER = """Propose ONE fresh, high-potential {niche} topic for our next 60-second Short.
Language: {language}

Forensic findings (patterns to apply, NOT subjects to copy):
{findings}

Recently covered topics (DO NOT repeat any of these — pick a different subject, even if from the same theme pool):
{recent}

PREFERRED TOPIC POOLS — ~70% of topics MUST come from these regions/themes (the channel's identity):

TURKIC & OTTOMAN (strong emphasis):
- Turkic/Central Asian empires: Xiongnu, Göktürks, Seljuks, Timurids, Mongols (Genghis Khan, Modu Chanyu/Mete Han, Attila, Timur, Bumin Qaghan, Tughril, Alp Arslan)
- Ottoman Empire: sultans, sieges, Janissaries, naval battles, harem intrigue, conquests, collapse (Mehmed II, Suleiman, Selim, Murad, Roxelana, Sinan, Barbarossa)
- East Turkestan (Uyghur history, Dzungar genocide, Qing conquest, Kashgar, Silk Road Turkic kingdoms)

ROME: republic crises, emperors (famous AND obscure), legions, gladiators, plagues, late-empire collapse, Byzantine offshoots.

GREAT BATTLES & MILITARY HISTORY: Gaugamela, Cannae, Manzikert, Ankara, Varna, Mohács, Vienna, Lepanto, Trafalgar, Waterloo, Gallipoli, Verdun, Stalingrad, Kursk, Midway, Inchon, lesser-known decisive clashes.

MAJOR NATIONAL HISTORIES (draw from any):
- China: dynasties (Qin, Han, Tang, Song, Ming, Qing), warlords, Taiping, Boxer, Cultural Revolution, forgotten emperors
- Russia: Tsars, Rurik, Ivan the Terrible, Peter, Catherine, Rasputin-era, Stalin, gulags, Cold War
- Japan: samurai, shoguns, Sengoku, Meiji Restoration, WWII (Pearl Harbor, Midway, kamikaze, Nanking), emperors
- North & South Korea: Three Kingdoms, Joseon, Japanese occupation, Korean War, DMZ, Kim dynasty
- Germany: Holy Roman Empire, Prussia, Bismarck, Weimar, Third Reich, Stasi, Berlin Wall
- England/UK: Tudors, Stuarts, Elizabeth I, empire, Churchill, WWII, Cromwell, Napoleon-era
- France: Gauls, Franks, Crusades, Louis XIV, Revolution, Napoleon, WWII resistance
- America/USA: founding, Civil War, presidents, frontier, WWII, Cold War, CIA operations, forgotten conflicts
- Greece: Mycenaean, Persian Wars, Peloponnesian, Alexander, Hellenistic, Byzantine

~30% OTHER: any history worth telling — Africa, South America, India, Southeast Asia, Middle East beyond Ottoman, inventors, plagues, disasters, cover-ups, mysteries.

Diversity rules:
- If the last 5 topics all came from the same country/empire, deliberately pick a different one
- Within a region, pick a different figure/era than the last one from that region
- Specific > vague: "Mete Han's wedge formation at the Battle of Baideng 200 BC" beats "Ancient Turkic warfare"
- Hook on the darkest/weirdest angle, not the textbook summary

Return JSON:
{{
  "topic": string,                  // 1-line topic specific enough to script (include names/dates)
  "angle": string,                  // the hook/angle that differentiates it
  "why": string,                    // why this will beat competitors
  "pool": string,                   // turkic-ottoman / east-turkestan / rome / great-battle / china / russia / japan / korea / germany / uk / france / usa / greece / other
  "era": string,                    // ancient/medieval/early-modern/industrial/20th/contemporary
  "region": string                  // Asia/Europe/Africa/Americas/Middle-East/Oceania
}}"""


HISTORY_FILE_REL = "pipeline/topic_history.json"


def _load_recent_topics(root: Path, workspace_dir: Path, limit: int = 25) -> list[str]:
    """Collect recent topics from the committed history file, falling back to local workspace."""
    topics: list[str] = []
    # 1. Persistent history (committed to repo, survives across cloud runs)
    history_file = root / HISTORY_FILE_REL
    if history_file.exists():
        try:
            data = json.loads(history_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                topics.extend(str(x).strip() for x in data if x)
        except Exception:
            pass
    # 2. Local workspace fallback (useful on dev machine before first commit)
    if workspace_dir.exists():
        try:
            run_dirs = sorted(
                [d for d in workspace_dir.iterdir() if d.is_dir()],
                key=lambda p: p.name,
                reverse=True,
            )
        except Exception:
            run_dirs = []
        for d in run_dirs:
            tp = d / "topic.json"
            if not tp.exists():
                continue
            try:
                data = json.loads(tp.read_text(encoding="utf-8"))
                t = (data.get("topic") or "").strip()
                if t and t not in topics:
                    topics.append(t)
            except Exception:
                continue
    # dedupe preserving order, take most recent `limit`
    seen = set()
    uniq: list[str] = []
    for t in topics:
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)
    return uniq[-limit:]


def append_topic_to_history(root: Path, topic: str) -> None:
    """Append topic to the committed history file."""
    history_file = root / HISTORY_FILE_REL
    history: list[str] = []
    if history_file.exists():
        try:
            data = json.loads(history_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                history = [str(x) for x in data if x]
        except Exception:
            pass
    history.append(topic.strip())
    # cap at 200 to keep file small
    history = history[-200:]
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text(json.dumps(history, indent=2), encoding="utf-8")


def choose_topic(settings: Settings, findings: dict[str, Any]) -> dict[str, Any]:
    recent = _load_recent_topics(settings.root, settings.workspace_dir)
    if recent:
        recent_block = "\n".join(f"- {t}" for t in recent)
    else:
        recent_block = "(no prior topics)"
    return call_json(
        settings,
        SYSTEM.format(niche=settings.niche),
        USER.format(
            niche=settings.niche,
            language=settings.language,
            findings=json.dumps(findings, indent=2),
            recent=recent_block,
        ),
        max_tokens=900,
        temperature=0.95,
    )
