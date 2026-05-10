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

USER = """Propose ONE fresh, high-potential topic for our next 60-second Short.
Language: {language}

This channel covers THREE equally-weighted content categories on strict rotation:
  A) HISTORY     — empires, rulers, battles, dynasties, classical events (verified history)
  B) REAL-EVENTS — true real-life events from modern era: survivals, crimes, cover-ups,
                   discoveries, disasters, escapes, true stories that actually happened
  C) PARANORMAL  — real-world unexplained / paranormal cases: hauntings, UFO incidents,
                   unexplained disappearances, cryptid sightings, occult/cult events

Forensic findings (patterns to apply, NOT subjects to copy):
{findings}

Recently covered topics (HARD BAN — read carefully):
{recent}

SUBJECT-LEVEL DEDUPLICATION (this is the most common failure mode — read twice):
- The check above is NOT just string matching. If ANY central figure, event, battle, or location from a recent topic also appears in your proposed topic, the topic is REJECTED. Examples:
  * Recent: "Genghis Khan's death cover-up" → BANNED any new Genghis Khan topic.
  * Recent: "Rasputin assassination" → BANNED any topic featuring Rasputin or Yusupov.
  * Recent: "Battle of Manzikert 1071" → BANNED any topic about Romanos IV or Alp Arslan.
  * Recent: "Dyatlov Pass incident" → BANNED any new Dyatlov topic, even a different angle.
- Rephrasing the same story with new wording is the #1 way this rule gets broken. Do NOT do it.
- "Same era, different person" is fine. "Same person/event, different angle" is NOT fine.

Recently used categories (last 6 videos, newest first):
{recent_categories}

Recently used story formats (last 5, newest first):
{recent_formats}

CATEGORY ROTATION — HARD RULE (most important rule on this page):
- The 3 categories MUST rotate strictly: A → B → C → A → B → C ...
- Look at the LAST category fired (top of the list above). THIS run MUST pick a DIFFERENT category.
- If the last category was HISTORY → THIS run picks REAL-EVENTS or PARANORMAL.
- If the last category was REAL-EVENTS → THIS run picks PARANORMAL or HISTORY.
- If the last category was PARANORMAL → THIS run picks HISTORY or REAL-EVENTS.
- Across the last 6 videos, all 3 categories MUST appear at least once. If any category is missing from the last 6, you MUST pick that missing category this run.
- Equal long-run mix target: 1/3 HISTORY, 1/3 REAL-EVENTS, 1/3 PARANORMAL.

FORMAT MENU (12 formats, 4 per category — pick exactly one):

  CATEGORY A — HISTORY:
  1. "violent-ruler"            — emperor/sultan/khan personal cruelty + body counts
  2. "decisive-battle"          — single battle that changed history (tactics, betrayal, casualties)
  3. "underdog-victory"         — outnumbered force wins (Thermopylae, Agincourt, Stalingrad-style)
  4. "forgotten-woman"          — overlooked female figure who changed events (Boudica, Tomyris, Hatshepsut)

  CATEGORY B — REAL-EVENTS:
  5. "survival-escape"          — captivity/escape/lone-survivor story (Shackleton, Hugh Glass, Aron Ralston, Juliane Koepcke)
  6. "true-crime"               — real criminal cases (Zodiac, D.B. Cooper, Tylenol murders, the Iceman, Belle Gunness)
  7. "modern-coverup"           — government/corporate cover-ups (MK-Ultra, Tuskegee, Tonkin, Watergate, Bhopal)
  8. "discovery-disaster"       — true discovery/invention/disaster with dark twist (radium girls, Chernobyl, Therac-25, Bhopal)

  CATEGORY C — PARANORMAL:
  9. "haunting-case"            — verified haunted house / poltergeist case (Enfield, Amityville, Bell Witch, Borley Rectory, Smurl)
  10. "ufo-encounter"           — documented UFO incidents (Roswell, Phoenix Lights, Rendlesham, Tic Tac, Travis Walton, Westall)
  11. "unexplained-disappearance" — paranormal-tinged vanishings (Dyatlov Pass, Flight 19, Bermuda Triangle, Roanoke, Missing 411, MH370)
  12. "occult-cryptid"          — cryptid sightings, occult / curse / cult events (Mothman, Skinwalker Ranch, Hexham Heads, Tunguska, Heaven's Gate)

DIVERSITY WITHIN A CATEGORY:
- HISTORY: do NOT default to Rome or Ottoman every time. The recent topic list shows what's been overused — actively pick OTHER regions: China, Russia, Japan, Korea, India, Africa, South America, Persia, pre-Columbian, Vikings, Celts, etc. If the last 4 history videos were all Rome/Byzantine/Ottoman, this one MUST be from a different region.
- REAL-EVENTS: span 19th-21st century, global. Don't keep returning to WW2 only.
- PARANORMAL: span the full canon. Don't default to UFO only — rotate hauntings, disappearances, cryptids, occult.

GENERAL RULES:
- Specific > vague: "Mete Han's wedge formation at Baideng 200 BC" beats "Ancient Turkic warfare". "The Tic Tac UFO encounter, USS Nimitz 2004" beats "Famous UFO sightings."
- Hook on the darkest/weirdest angle, not the textbook summary.
- For PARANORMAL: anchor in REAL DOCUMENTED cases (police reports, military records, named witnesses, dates). Do NOT make up fake stories. The angle is "this actually happened and nobody can explain it" — never "here is a scary fictional tale."

Return JSON:
{{
  "topic": string,                  // 1-line topic specific enough to script (include names/dates)
  "angle": string,                  // the hook/angle that differentiates it
  "why": string,                    // why this will beat competitors
  "category": string,               // EXACTLY one of: history / real-events / paranormal
  "format": string,                 // one of the 12 format slugs above
  "pool": string,                   // for history: turkic-ottoman/rome/byzantine/china/russia/japan/korea/germany/uk/france/usa/greece/other ; for real-events: survival/true-crime/coverup/disaster ; for paranormal: haunting/ufo/disappearance/cryptid-occult
  "era": string,                    // ancient/medieval/early-modern/industrial/20th/contemporary
  "region": string                  // Asia/Europe/Africa/Americas/Middle-East/Oceania
}}"""


# Maps each format slug to its parent category. Single source of truth used by
# both the rotation logger and (implicitly) for any future analytics.
FORMAT_TO_CATEGORY: dict[str, str] = {
    # history
    "violent-ruler": "history",
    "decisive-battle": "history",
    "underdog-victory": "history",
    "forgotten-woman": "history",
    # real-events
    "survival-escape": "real-events",
    "true-crime": "real-events",
    "modern-coverup": "real-events",
    "discovery-disaster": "real-events",
    # paranormal
    "haunting-case": "paranormal",
    "ufo-encounter": "paranormal",
    "unexplained-disappearance": "paranormal",
    "occult-cryptid": "paranormal",
    # legacy formats kept for backward-compat with existing topic_meta.json
    "cover-up-mystery": "real-events",
    "invention-shock": "real-events",
    "strange-tradition": "real-events",
}


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
    root: Path, topic: str, pool: str, fmt: str, category: str = ""
) -> None:
    """Append {topic, pool, format, category} to the parallel metadata log."""
    meta_file = root / META_FILE_REL
    log: list[dict[str, str]] = []
    if meta_file.exists():
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                log = [d for d in data if isinstance(d, dict)]
        except Exception:
            pass
    # Derive category from format if caller didn't pass one.
    cat = (category or "").strip().lower()
    if not cat:
        cat = FORMAT_TO_CATEGORY.get(fmt, "history")
    log.append({
        "topic": topic.strip(),
        "pool": pool or "other",
        "format": fmt or "",
        "category": cat,
    })
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


def _build_recent_categories(meta: list[dict[str, str]], window: int = 6) -> str:
    """Show last `window` categories (newest first), inferred from format if absent."""
    if not meta:
        return "(none)"
    recent = meta[-window:]
    rows: list[str] = []
    for entry in reversed(recent):  # newest first
        cat = (entry.get("category") or "").strip()
        if not cat:
            fmt = (entry.get("format") or "").strip()
            cat = FORMAT_TO_CATEGORY.get(fmt, "history")  # legacy default
        rows.append(f"- {cat}")
    # Also show which categories are MISSING from the window — drives the
    # "must pick missing category" rule.
    seen = {(entry.get("category") or FORMAT_TO_CATEGORY.get(entry.get("format", ""), "history"))
            for entry in recent}
    missing = [c for c in ("history", "real-events", "paranormal") if c not in seen]
    if missing:
        rows.append(f"** MISSING from last {window} (you MUST pick one of these): {', '.join(missing)} **")
    return "\n".join(rows)


def choose_topic(settings: Settings, findings: dict[str, Any]) -> dict[str, Any]:
    recent = _load_recent_topics(settings.root, settings.workspace_dir)
    if recent:
        recent_block = "\n".join(f"- {t}" for t in recent)
    else:
        recent_block = "(no prior topics)"
    meta = _load_recent_metadata(settings.root)
    recent_categories = _build_recent_categories(meta, window=6)
    recent_formats = _build_recent_formats(meta, window=5)
    return call_json(
        settings,
        SYSTEM.format(niche=settings.niche),
        USER.format(
            language=settings.language,
            findings=json.dumps(findings, indent=2),
            recent=recent_block,
            recent_categories=recent_categories,
            recent_formats=recent_formats,
        ),
        max_tokens=900,
        temperature=0.95,
    )
