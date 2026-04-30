# Silent Capital — Project Postmortem

**Status:** Paused (effectively cancelled). Code preserved on `silent-capital` branch.
**Duration:** 4 days (2026-04-28 to 2026-04-30)
**Outcome:** Strategy invalidated by reality before more time/money sunk. Engine kept as portfolio piece.

---

## What this project was

A faceless YouTube Shorts engine targeting the "money psychology" niche
under the brand **Silent Capital**. Forked from
[`0gebey/youtube-shorts-pipeline`](https://github.com/0gebey/youtube-shorts-pipeline)
and rebuilt around a custom intelligence layer:

```
Headline (Telegram)
  → OpenRouter (Claude 4.5 with CHANNEL_DNA + CONTENT_LAW + PROMPT_LAW prompt composer)
  → Script JSON (hook, pivot, mechanism, takeaway)
  → Scene plan (8-10 visuals)
  → Pexels Photos / Videos
  → ElevenLabs voiceover (George, slowed to 0.9x)
  → Whisper word-level captions (Helvetica Neue 96pt, libass burn-in)
  → Background music (loudnorm + dynamic ducking)
  → ffmpeg assembly (1080x1920 h264 + AAC)
  → Telegram approval bot (Approve / Reject / Regen)
  → Manual upload to YouTube Studio
```

Goal: ₹50k–1L/month from Shorts ad revenue + later affiliate income.

---

## What was actually built (commits on `silent-capital`)

| Phase | Commit | Notes |
|---|---|---|
| Phase 1 | `74eaece` | CHANNEL_DNA.json, CONTENT_LAW.md, PROMPT_LAW.md (editorial guardrails) |
| Phase 2 | `b94a076` | OpenRouter client + prompt composer + script generation |
| Phase 3 + 4 | `fffa105` | scene_builder + Pexels Photos visual fetcher |
| Phase 5 | `0fd8f7f` | Telegram approval bot |
| Phase 5+ | `aecd32f` | Telegram trigger bot + upload metadata in approval message |
| Reminders | `73e0b0d` | Daily 12:25/19:55 reminder thread |
| Quality | `88fb14b`, `dfb591c`, `d342b3f` | 10-frame pacing, ElevenLabs tuning, music balance |
| Retention fix | `b4afe88` | 24-32s target with mid-script verbal pivot |
| Render fixes | `81315f0`, `a56441b` | ffmpeg ass-filter quote escape + libass auto-skip |
| WIP refactor | `f3934f0` | Per-client config architecture + Pexels Videos (incomplete) |

Total: ~13 commits, ~3000 lines, 4 evenings of work.

---

## Real performance data (the kill signal)

### Short #1 — "Why EMI Tricks Smart People Too" (53 seconds)
- **Final views**: 785 (plateaued)
- **Stayed to watch**: 49.4% ✅ (hook worked)
- **Avg % viewed**: 28.7% ❌ (this killed it)
- **Subscribers gained**: 0 ❌ (the structural verdict)

### Short #2 — "Why Your Brain Treats Discounts as Profit" (28 seconds, new format)
- **Final views**: 12 (algorithm refused to test it)
- **Stayed to watch**: 27.3% ❌
- **Avg % viewed**: 64.6% ✅ (retention fix worked)
- **Subscribers gained**: 0

The retention fix worked. **The channel-level signal was the dealbreaker** —
algorithm-distrust from Short #1 + the structural problem of zero
sub-conversion in this niche meant Short #2 never got a real test pool.

### YouTube Shorts revenue reality
- **Shorts RPM**: $0.01–$0.07 per 1,000 views (researched against 30+ 2026 sources)
- **Long-form finance RPM**: $10–$25 per 1,000 views (300–1000x more)
- **Implication**: Shorts are a discovery tool, not a revenue path. Even
  1M Shorts views = $10–70 in ad revenue.

---

## Why we killed it

Two compounding structural problems, neither fixable by more iteration:

### 1. Faceless format ≠ subscriber growth in this niche
- Money psychology is "value extracted, no reason to return" content
- Without a face, no parasocial bond → no subscription trigger
- Sub conversion floor in this niche/format: 0–2 subs per 1,000 views
- Compare: faceless true-crime channels convert at 20–50 subs/1k

### 2. The productized service market doesn't exist either
- Successful Indian finance creators (Pranjal Kamra, Akshat Shrivastava,
  Ankur Warikoo, Sharan Hegde) all use their faces
- Creators who'd theoretically benefit from this engine (faceless
  finance Shorts) aren't growing → can't pay ₹15k/month
- Selling to face-on-camera creators would require pivot to long-form
  cutting, not Shorts generation
- B2C SaaS in this space is brutally saturated (Pictory, InVideo,
  Submagic, Opus Clip — all funded competitors)

In short: there's no business here, and the channel itself can't grow.

---

## What's salvageable

### The engine itself is solid
- ~3000 lines of working Python
- Generates production-quality 1080x1920 Shorts in ~2 minutes
- Cost per video: ~₹8–10 in API charges
- Telegram-driven, runs on a Mac, no infrastructure needed
- Handles ElevenLabs + OpenRouter + Pexels + Whisper + ffmpeg + libass + music ducking

### What pivots cleanly
If a future use case appears, the engine adapts to:
- **True crime narration** — same engine, swap CONTENT_LAW + prompts
- **Story narration / history** — same engine, different DNA
- **Long-form package generator** — extend script length cap, add chart auto-gen
- **White-label SaaS for face-cam creators** — needs rebuild, but core pipeline transfers

### The per-client architecture (WIP in commit `f3934f0`)
- `clients/<name>/` folders for per-tenant config
- Was 80% complete when project paused
- Would need 2-3 hours to wire CLI flag + bot routing + smoke test

---

## Lessons (the actual ROI of these 4 days)

1. **Validate distribution before production.** I built the engine assuming the
   channel format would work. Should have done 5 manual scripts + face-cam
   selfies first to test if the niche has audience pull. 4 days of code on
   a dead niche.

2. **YouTube Shorts ad revenue is a myth for new channels.** The "make money
   with AI Shorts" content on YouTube and Twitter is largely lying. Real
   numbers: ₹0.83–₹5.83 per 1,000 views. Long-form is where real money lives.

3. **Faceless wins in only ~3 niches.** True crime, story narration,
   compilation. Everything else requires a face for parasocial bonding,
   which drives subscription conversion, which drives the algorithm's
   decision to expand reach.

4. **Channel-level reputation compounds fast.** One bad video (785 views,
   28% APV) tanked the test pool for video #2 (12 views) within 24 hours.
   Cold-start problem is real.

5. **AI video generation is still cost-prohibitive for service businesses.**
   Sora/Runway/Veo at $0.50–2.00 per clip × 8 clips/Short = ₹400–800/Short
   in just video. Pexels stock video (free) + Pexels photos still beats it
   on margin. Real stock video > AI generated video for most realistic scenes.

6. **The "build first, sell later" trap is real.** Always start with 5–10
   conversations about a real painful workflow before writing code. Charge
   ₹500/month from day 1. Real revenue is the only signal that matters.

---

## How to revive this project (if ever)

If you come back to this in 6 months / 2 years / never:

### To use the engine for a different niche:
```bash
# 1. Create a new client folder
cp -r clients/silent_capital clients/<new_name>
# 2. Edit clients/<new_name>/CHANNEL_DNA.json with new niche
# 3. Optionally override prompts in clients/<new_name>/prompts/
# 4. Drop your own music tracks in clients/<new_name>/music/
# 5. Wire the CLI flag (the WIP from commit f3934f0)
SILENT_CAPITAL_CLIENT=<new_name> .venv/bin/python -m pipeline bot
```

### To finish the WIP refactor (~2 hours):
1. Add `--client <name>` flag to `pipeline/__main__.py` argparse
2. In `silent_capital/bot_listener.py`, accept `--client` or load
   `TELEGRAM_CHAT_TO_CLIENT_MAP` env var (chat_id → client name)
3. Smoke test: `SILENT_CAPITAL_CLIENT=silent_capital .venv/bin/python -m pipeline bot`
   send a headline, verify the per-client config loads end to end

### To productize as a service (if market emerges):
- Path 1: cut Shorts from face-cam creators' long-form videos (Opus Clip clone, narrower wedge)
- Path 2: regional language Shorts for underserved Indian creators (Tamil/Telugu/Marathi finance)
- Skip: generic "AI Shorts generator" SaaS — saturated, no wedge

---

## Files of interest

| File | Purpose |
|---|---|
| `pipeline/__main__.py` | CLI entry: draft / produce / approve / bot commands |
| `pipeline/draft.py` | OpenRouter script generation via prompt composer |
| `pipeline/broll.py` | Pexels Video → Photo → Imagen fallback chain |
| `pipeline/assemble.py` | ffmpeg pipeline (handles mixed video + photo) |
| `pipeline/voiceover.py` | ElevenLabs (slowed 0.9x) + macOS `say` fallback |
| `pipeline/music.py` | Random track + duck filter (loudnorm normalized) |
| `pipeline/captions.py` | Whisper word timing + per-client ASS style |
| `silent_capital/openrouter_client.py` | JSON-mode API wrapper with retry |
| `silent_capital/prompt_composer.py` | Per-client DNA injection |
| `silent_capital/client_config.py` | Per-tenant config loader (NEW, WIP) |
| `silent_capital/visual_fetcher.py` | Pexels Photos + Videos fetchers |
| `silent_capital/scene_builder.py` | Script → scene plan (unused but kept) |
| `silent_capital/telegram_bot.py` | Approval flow with inline buttons |
| `silent_capital/bot_listener.py` | Headline → render → approve loop + reminders |
| `clients/silent_capital/` | Silent Capital brand config (DNA, voice, music) |
| `clients/shared/` | Default config fallbacks |
| `prompts/script_prompt.txt` | Active prompt (24-32s, pivot_line structure) |

---

## Cost summary

- **Total spent**: ~₹150 (OpenRouter + ElevenLabs free tier)
- **Time invested**: ~16 hours of building + testing
- **Revenue earned**: ₹0
- **Learning value**: high (see Lessons section)

Net: a cheap, fast, complete experiment. The right kind of failure.

---

*Closed out 2026-04-30. The repo stays. The strategy doesn't.*
