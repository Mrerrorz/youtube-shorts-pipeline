# music/

Drop royalty-free MP3 tracks here. The pipeline picks one at random per video
and ducks volume during voiceover automatically.

## Recommended sources (CC0 / royalty-free)

- **Pixabay Music** — https://pixabay.com/music/ (no attribution required)
- **YouTube Audio Library** — https://studio.youtube.com → Audio Library
- **Free Music Archive** — https://freemusicarchive.org (filter by CC0)
- **Uppbeat** — https://uppbeat.io (free tier with attribution)

## What to look for (Silent Capital DNA)

- Ambient, calm, observational
- No vocals
- 90-110 BPM
- 60-120 seconds long
- Low-key piano, soft pads, lo-fi business documentary feel

Avoid: aggressive trap, motivational stings, generic "epic cinematic" — these
clash with the "calm authority" voice style.

## How it's used

`pipeline/music.py` picks a random `.mp3` from this folder and applies a duck
filter so it drops to ~15% volume while the voiceover is speaking. If this
folder is empty, videos render without background music (still valid).
