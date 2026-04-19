# YouTube Shorts Auto Pipeline (History niche)

Takes competitor Shorts URLs → analyzes → writes new script → TTS → renders vertical video → uploads to YouTube.

## Stack
- **Python** orchestrator (`main.py` + `pipeline/`)
- **Anthropic Claude** — forensic analysis, titles, script
- **ElevenLabs** — voiceover
- **Remotion** — 1080x1920 render (`src/Shorts.tsx`)
- **YouTube Data API v3** — upload

## Setup

### 1. Install dependencies
```bash
npm install
pip install -r requirements.txt
```

### 2. Fill in secrets
Copy `.env.example` to `.env` and add keys.

Place `client_secret.json` (Google Cloud OAuth Desktop client) at repo root.

### 3. Add competitor URLs
Edit `urls.txt` — one Shorts URL per line.

### 4. Run
```bash
# Dry run (no upload, no render) — just script + voice
python main.py --urls-file urls.txt --skip-render

# Full pipeline
python main.py --urls-file urls.txt
```

First run triggers a browser OAuth flow. Token is cached in `token.json`.

## Output layout
```
workspace/<timestamp>/
  transcripts.json
  findings.json
  topic.json
  title.json
  script.json
  voice.mp3
  subtitles.json
  short.mp4
  youtube_url.txt
```

## Preview in Remotion Studio
```bash
npm run dev
# Select the "Shorts" composition.
# Put voice.mp3 + subtitles.json into /public to preview real content.
```

## Flags
- `--topic "..."` — override auto-picked topic
- `--skip-render` — stop after TTS
- `--skip-upload` — render but don't upload
