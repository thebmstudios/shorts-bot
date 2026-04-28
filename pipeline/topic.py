"""Pick a fresh topic based on forensic findings. Avoids repeating recent subjects."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Settings
from .llm import call_json

SYSTEM = """You are a content strategist for a {niche} Shorts channel.
You MUST avoid repeating subjects, figures, or events that appear in the "Recently covered" list.
You MUST also vary the POOL (region/empire) and FORMAT (story type) — channels die when every video feels the same.
Output MUST be JSON only."""

USER = """Propose ONE fresh, high-potential {niche} topic for our next 60-second Short.
Language: {language}

Forensic findings (patterns to apply, NOT subjects to copy):
{findings}

Recently covered topics (DO NOT repeat any of these — pick a different subject, even if from the same theme pool):
{recent}

Recently used pools (count of last 10 videos by region/empire):
{pool_counts}

Recently used story formats (last 5, newest first):
{recent_formats}

POOL COOLDOWN — HARD RULE:
- If any pool above has 3 or more uses in the last 10 videos, that pool is BANNED for this run. Pick a different pool.
- If a pool has 2 uses, prefer something else unless it's the ONLY untouched relevant option.

FORMAT DIVERSITY — HARD RULE:
- Do NOT repeat the format of the last video. Rotate.
- The 8 formats this channel uses (pick ONE that did NOT appear in the last 3):
  1. "violent-ruler"     — emperor/sultan/khan personal cruelty + body counts
  2. "decisive-battle"   — single battle that changed history (tactics, betrayal, casualties)
  3. "underdog-victory"  — outnumbered force wins (Thermopylae, Agincourt, Stalingrad-style)
  4. "cover-up-mystery"  — disappearance, faked death, lost treasure, censored event
  5. "invention-shock"   — discovery/invention with a dark twist (mercury cures, lobotomy, gunpowder)
  6. "forgotten-woman"   — overlooked female figure who changed events (Boudica, Tomyris, Trotula, Hatshepsut)
  7. "survival-escape"   — captivity/escape/lone-survivor story (Shackleton, Hugh Glass, Witold Pilecki)
  8. "strange-tradition" — bizarre ritual/practice that actually existed (sky burials, mellified man)

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
  "pool": string,                   // turkic-ottoman / east-turkestan / rome / byzantine / great-battle / china / russia / japan / korea / germany / uk / france / usa / greece / other
  "format": string,                 // one of: violent-ruler / decisive-battle / underdog-victory / cover-up-mystery / invention-shock / forgotten-woman / survival-escape / strange-tradition
  "era": string,                    // ancient/medieval/early-modern/industrial/20th/contemporary
  "region": string                  // Asia/Europe/Africa/Americas/Middle-East/Oceania
}}"""


HISTORY_FILE_REL = "pipeline/topic_history.json"
META_FILE_REL = "pipeline/topic_meta.json"  # parallel pool/format log


# Cheap heuristic: classify a topic string into a pool when we have no metadata
# (used for the legacy string-only entries already in topic_history.json).
_POOL_KEYWORDS: list[tuple[str, list[str]]] = [
    ("byzantine", ["byzanti", "constantinople", "justinian", "theodora", "basil ii",
                   "bulgar-slayer", "phocas", "irene", "manzikert", "nika"]),
    ("turkic-ottoman", ["ottoman", "sultan", "janissar", "suleiman", "mehmed",
                        "murad", "bayezid", "topkapi", "devshirme", "mete han",
                        "modu chanyu", "xiongnu", "seljuk", "alp arslan",
                        "timur", "tamerlane"]),
    ("rome", ["roman ", " rome", "caesar", "valerian", "majorian", "elagabalus",
              "macrinus", "julia maesa", "crassus", "carrhae", "augustus", "nero"]),
    ("china", ["chinese", "ming ", "qing", "tang", "han ", "qin ", "hongwu",
               "zhu yuanzhang", "qin shi huang", "boxer", "taiping",
               "ching shih"]),
    ("russia", ["russia", "tsar", "stalin", "rasputin", "ivan the terrible",
                "peter the great", "catherine"]),
    ("japan", ["japan", "samurai", "shogun", "sengoku", "meiji", "kamikaze"]),
    ("korea", ["korea", "joseon", "kim il", "kim jong"]),
    ("germany", ["germany", "prussia", "bismarck", "weimar", "reich", "stasi"]),
    ("uk", ["england", "tudor", "elizabeth i", "cromwell", "churchill"]),
    ("france", ["france", "napoleon", "bourbon", "louis xiv", "robespierre"]),
    ("usa", [" usa ", "america", "lincoln", "civil war", "washington", "jefferson",
             "kennedy", " cia "]),
    ("greece", ["greek", "athens", "sparta", "thermopylae", "alexander the great",
                "peloponnes"]),
    ("east-turkestan", ["uyghur", "kashgar", "dzungar"]),
    ("great-battle", ["battle of "]),
    ("mongol", ["genghis", "mongol", "kublai"]),
]


def _infer_pool(topic: str) -> str:
    t = topic.lower()
    for pool, kws in _POOL_KEYWORDS:
        if any(kw in t for kw in kws):
            return pool
    return "other"


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


def append_topic_metadata(
    root: Path, topic: str, pool: str, fmt: str
) -> None:
    """Append {topic, pool, format} to the parallel metadata log."""
    meta_file = root / META_FILE_REL
    log: list[dict[str, str]] = []
    if meta_file.exists():
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                log = [d for d in data if isinstance(d, dict)]
        except Exception:
            pass
    log.append({"topic": topic.strip(), "pool": pool or "other", "format": fmt or ""})
    log = log[-200:]
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    meta_file.write_text(json.dumps(log, indent=2), encoding="utf-8")


def _load_recent_metadata(root: Path) -> list[dict[str, str]]:
    """Load {topic, pool, format} log; backfill from string history if missing."""
    meta_file = root / META_FILE_REL
    if meta_file.exists():
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict)]
        except Exception:
            pass
    # Backfill from legacy string history with inferred pools.
    history_file = root / HISTORY_FILE_REL
    if history_file.exists():
        try:
            topics = json.loads(history_file.read_text(encoding="utf-8")) or []
            return [
                {"topic": str(t), "pool": _infer_pool(str(t)), "format": ""}
                for t in topics
                if t
            ]
        except Exception:
            pass
    return []


def _build_pool_counts(meta: list[dict[str, str]], window: int = 10) -> str:
    """Render 'pool: N' lines for the last `window` videos."""
    if not meta:
        return "(none)"
    recent = meta[-window:]
    counts: dict[str, int] = {}
    for m in recent:
        pool = (m.get("pool") or "other").strip() or "other"
        counts[pool] = counts.get(pool, 0) + 1
    # Highlight banned pools (>=3) so the LLM sees the rule applied.
    rows = []
    for pool, n in sorted(counts.items(), key=lambda x: -x[1]):
        flag = "  <-- BANNED" if n >= 3 else ("  (cooldown: prefer different)" if n == 2 else "")
        rows.append(f"- {pool}: {n}{flag}")
    return "\n".join(rows)


def _build_recent_formats(meta: list[dict[str, str]], window: int = 5) -> str:
    if not meta:
        return "(none)"
    recent = [m.get("format", "").strip() for m in meta[-window:] if m.get("format")]
    if not recent:
        return "(none)"
    # Newest first
    recent = list(reversed(recent))
    return "\n".join(f"- {f}" for f in recent)


def choose_topic(settings: Settings, findings: dict[str, Any]) -> dict[str, Any]:
    recent = _load_recent_topics(settings.root, settings.workspace_dir)
    if recent:
        recent_block = "\n".join(f"- {t}" for t in recent)
    else:
        recent_block = "(no prior topics)"
    meta = _load_recent_metadata(settings.root)
    pool_counts = _build_pool_counts(meta, window=10)
    recent_formats = _build_recent_formats(meta, window=5)
    return call_json(
        settings,
        SYSTEM.format(niche=settings.niche),
        USER.format(
            niche=settings.niche,
            language=settings.language,
            findings=json.dumps(findings, indent=2),
            recent=recent_block,
            pool_counts=pool_counts,
            recent_formats=recent_formats,
        ),
        max_tokens=900,
        temperature=0.95,
    )
