"""Telegram trigger bot — listen for headlines, render shorts on demand.

Run with:  python -m pipeline bot

Behavior:
  - Long-polls Telegram for messages from TELEGRAM_CHAT_ID only (security gate).
  - /start, /help → reply with usage instructions.
  - Any other text → treat as a headline, run draft + produce, then send the
    rendered video back to chat with Approve/Reject/Regen buttons.
  - Inline button taps are also handled (approve copies to media/approved/).

This is the simplest possible "headline-to-Short" UX: type a headline on your
phone, get a publishable Short back in ~2 minutes.
"""

import json
import os
import shutil
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

import requests

API_BASE = "https://api.telegram.org/bot"
HELP_TEXT = (
    "*Silent Capital bot*\n\n"
    "Send me a headline (one per message) and I'll generate a Short.\n\n"
    "Examples:\n"
    "• Why EMI Tricks Smart People Too\n"
    "• Why Your Brain Treats Discounts as Profit\n"
    "• The Hidden Cost of Choosing the Middle Option\n\n"
    "I'll reply when the video is ready (~2 minutes). You then tap "
    "✅ Approve / ❌ Reject / 🔁 Regen on the rendered video.\n\n"
    "Approved videos are saved to `media/approved/` and the upload-ready "
    "title, description, tags, and Instagram caption are sent here too — "
    "ready to paste into YouTube Studio."
)


# Reminder slots: (hour, minute, label). Times are LOCAL machine time —
# set your Mac to IST or override REMINDER_SLOTS in env if you travel.
DEFAULT_SLOTS = [
    (12, 25, "afternoon (12:30 PM upload)"),
    (19, 55, "evening (8:00 PM upload)"),
]


def _parse_slots_env() -> list[tuple[int, int, str]]:
    """Allow overriding via env: REMINDER_SLOTS=12:25=afternoon,19:55=evening"""
    raw = os.environ.get("REMINDER_SLOTS", "").strip()
    if not raw:
        return DEFAULT_SLOTS
    out = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if "=" not in chunk:
            continue
        time_part, label = chunk.split("=", 1)
        try:
            h, m = time_part.split(":")
            out.append((int(h), int(m), label.strip()))
        except ValueError:
            continue
    return out or DEFAULT_SLOTS


def _reminder_loop(token: str, chat_id: str) -> None:
    """Background thread: fire one reminder per slot per day. Local time."""
    slots = _parse_slots_env()
    fired_today: dict[tuple[int, int], str] = {}

    while True:
        now = datetime.now()
        today_key = now.strftime("%Y-%m-%d")
        for h, m, label in slots:
            slot_id = (h, m)
            already = fired_today.get(slot_id)
            if already == today_key:
                continue
            if now.hour == h and now.minute == m:
                _send(token, chat_id,
                      f"🔔 *Reminder — {label}*\n\n"
                      f"Time to draft your next Short. Send a headline as a "
                      f"text message and I'll render it (~2 min).")
                fired_today[slot_id] = today_key
        time.sleep(30)


def _config() -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env."
        )
    return token, chat_id


def _send(token: str, chat_id: str, text: str) -> None:
    try:
        requests.post(
            f"{API_BASE}{token}/sendMessage",
            json={
                "chat_id": chat_id, "text": text,
                "parse_mode": "Markdown", "disable_web_page_preview": True,
            },
            timeout=30,
        )
    except Exception:
        pass


def _answer_callback(token: str, callback_id: str, text: str = "") -> None:
    try:
        requests.post(
            f"{API_BASE}{token}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": text},
            timeout=15,
        )
    except Exception:
        pass


def _handle_headline(token: str, chat_id: str, headline: str) -> None:
    """Run the full draft → produce pipeline, then send the video back."""
    from pipeline.draft import generate_draft
    from pipeline.broll import generate_broll
    from pipeline.voiceover import generate_voiceover
    from pipeline.captions import generate_captions
    from pipeline.music import select_and_prepare_music
    from pipeline.assemble import assemble_video
    from pipeline.config import DRAFTS_DIR, MEDIA_DIR
    from .telegram_bot import send_for_approval

    _send(token, chat_id, f"📝 Drafting: _{headline}_ ...")

    job_id = str(int(time.time()))
    draft = generate_draft(headline)
    draft["job_id"] = job_id

    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    draft_path = DRAFTS_DIR / f"{job_id}.json"
    draft_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False))

    _send(token, chat_id,
          f"🎙 Script ready. Producing video (Pexels + ElevenLabs + music)...")

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    work_dir = MEDIA_DIR / f"work_{job_id}_en"
    work_dir.mkdir(exist_ok=True)

    frames = generate_broll(draft.get("broll_prompts", []), work_dir)
    vo_path = generate_voiceover(draft["script"], work_dir, "en")
    captions_result = generate_captions(vo_path, work_dir, "en")
    music_result = select_and_prepare_music(vo_path, work_dir)
    video_path = assemble_video(
        frames=frames,
        voiceover=vo_path,
        out_dir=work_dir,
        job_id=job_id,
        lang="en",
        ass_path=captions_result.get("ass_path"),
        music_path=music_result.get("track_path"),
        duck_filter=music_result.get("duck_filter"),
    )

    draft["video_en"] = str(video_path)
    srt_p = captions_result.get("srt_path")
    if srt_p and Path(srt_p).exists():
        final_srt = MEDIA_DIR / f"pipeline_{job_id}_en.srt"
        shutil.copy(srt_p, final_srt)
        draft["srt_en"] = str(final_srt)
    draft_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False))

    send_for_approval(video_path, draft)


def _handle_callback(token: str, chat_id: str, cb: dict) -> None:
    """Process Approve/Reject/Regen taps on a sent video."""
    from pipeline.config import DRAFTS_DIR, MEDIA_DIR

    data = cb.get("data", "")
    if ":" not in data:
        return
    action, job_id = data.split(":", 1)

    _answer_callback(token, cb["id"], f"Got: {action}")

    draft_path = DRAFTS_DIR / f"{job_id}.json"
    if not draft_path.exists():
        _send(token, chat_id, f"⚠️ No draft found for job {job_id}.")
        return
    draft = json.loads(draft_path.read_text())
    video_path = Path(draft.get("video_en", ""))

    if action == "approve":
        approved_dir = MEDIA_DIR / "approved"
        approved_dir.mkdir(parents=True, exist_ok=True)
        if video_path.exists():
            shutil.copy(video_path, approved_dir / video_path.name)
        draft["approved"] = True
        draft_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False))
        _send(token, chat_id,
              f"✅ Approved. Saved to `media/approved/{video_path.name}`.\n"
              f"Upload to YouTube Studio using the metadata above.")
    elif action == "reject":
        rejected_dir = MEDIA_DIR / "rejected"
        rejected_dir.mkdir(parents=True, exist_ok=True)
        if video_path.exists():
            shutil.move(str(video_path), rejected_dir / video_path.name)
        draft["approved"] = False
        draft_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False))
        _send(token, chat_id, "❌ Rejected. Video moved to `media/rejected/`.")
    elif action == "regen":
        headline = draft.get("news", "")
        _send(token, chat_id, f"🔁 Regenerating: _{headline}_ ...")
        try:
            _handle_headline(token, chat_id, headline)
        except Exception as e:
            _send(token, chat_id, f"⚠️ Regen failed: {e}")


def run() -> None:
    token, allowed_chat_id = _config()
    slots = _parse_slots_env()
    slot_str = ", ".join(f"{h:02d}:{m:02d}" for h, m, _ in slots)
    print(f"Silent Capital bot listening (chat_id={allowed_chat_id}). Ctrl+C to stop.")
    print(f"Daily reminder slots (local time): {slot_str}")

    threading.Thread(
        target=_reminder_loop, args=(token, allowed_chat_id), daemon=True,
    ).start()

    _send(token, allowed_chat_id,
          f"🟢 *Silent Capital bot is online.*\n"
          f"Send a headline to generate a Short.\n\n"
          f"_Daily reminders set for {slot_str} (local time)._")

    offset = 0
    while True:
        try:
            r = requests.get(
                f"{API_BASE}{token}/getUpdates",
                params={"offset": offset, "timeout": 25,
                        "allowed_updates": json.dumps(["message", "callback_query"])},
                timeout=30,
            )
            if r.status_code != 200:
                time.sleep(3)
                continue
            body = r.json()
            if not body.get("ok"):
                time.sleep(3)
                continue

            for update in body.get("result", []):
                offset = update["update_id"] + 1

                # Inline button tap
                cb = update.get("callback_query")
                if cb:
                    cb_chat_id = str(cb.get("message", {}).get("chat", {}).get("id", ""))
                    if cb_chat_id != allowed_chat_id:
                        continue
                    try:
                        _handle_callback(token, allowed_chat_id, cb)
                    except Exception as e:
                        print(f"callback error: {e}")
                        traceback.print_exc()
                        _send(token, allowed_chat_id, f"⚠️ Callback error: {e}")
                    continue

                # Text message
                msg = update.get("message") or {}
                msg_chat_id = str(msg.get("chat", {}).get("id", ""))
                if msg_chat_id != allowed_chat_id:
                    continue
                text = (msg.get("text") or "").strip()
                if not text:
                    continue

                if text in ("/start", "/help"):
                    _send(token, allowed_chat_id, HELP_TEXT)
                    continue

                # Treat anything else as a headline
                try:
                    _handle_headline(token, allowed_chat_id, text)
                except Exception as e:
                    print(f"headline error: {e}")
                    traceback.print_exc()
                    _send(token, allowed_chat_id, f"⚠️ Pipeline failed: {e}")

        except KeyboardInterrupt:
            print("\nShutting down.")
            _send(token, allowed_chat_id, "🔴 Bot stopped.")
            return
        except Exception as e:
            print(f"loop error: {e}")
            time.sleep(5)
