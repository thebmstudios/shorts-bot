# Background music tracks

Drop royalty-free MP3 files here with these EXACT filenames so the bot can
pick the right music per content category:

| Filename             | Category    | Suggested vibe          |
|----------------------|-------------|-------------------------|
| `01_suspense.mp3`    | real-events | Cinematic suspense      |
| `02_dark_doc.mp3`    | history     | Dark documentary        |
| `03_historical.mp3`  | history     | Historical drama        |
| `04_tension.mp3`     | real-events | Tension ambient         |
| `05_mystery.mp3`     | paranormal  | Mystery cinematic       |
| `06_epic.mp3`        | history     | Epic dramatic           |
| `07_paranormal.mp3`  | paranormal  | Horror ambient drone    |

## Where to find tracks

All FREE, no YouTube copyright claim risk:

- **Pixabay Music** — https://pixabay.com/music/  (CC0, no attribution)
- **YouTube Audio Library** — https://www.youtube.com/audiolibrary
- **Mixkit** — https://mixkit.co/free-stock-music/

Search keywords: "cinematic suspense", "dark documentary", "historical
drama", "tension ambient", "mystery cinematic", "epic dramatic",
"horror ambient drone".

## How it works

`pipeline/render.py` looks at the topic's category (history / real-events /
paranormal) and picks a matching track at random. If a track is missing,
the bot falls back to ANY available .mp3 in this folder. If the folder is
empty, the video is rendered with voiceover only (no music) — back-compat.

Music is mixed at ~13% volume under the voiceover, with 0.4s fade-in and
0.6s fade-out so it never cold-starts or hard-cuts.
