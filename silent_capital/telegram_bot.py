"""Telegram approval bot — sends rendered video for human review.

Replaces the web dashboard from the original PRD. You approve from your phone,
no server to host. Uses direct HTTP calls to Telegram Bot API (no extra deps).

Setup:
  1. Create a bot via @BotFather on Telegram → copy the token.
  2. Send /start to your new bot.
  3. Run scripts/setup_telegram.py to discover your chat_id.
  4. Add to .env:
       TELEGRAM_BOT_TOKEN=...
       TELEGRAM_CHAT_ID=...
"""

import os
import time
from pathlib import Path

import requests

API_BASE = "https://api.telegram.org/bot"
SEND_VIDEO_TIMEOUT = 120
POLL_INTERVAL = 3
DEFAULT_APPROVAL_TIMEOUT = 60 * 30  # 30 min


class TelegramConfigError(RuntimeError):
    pass


def _get_config() -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise TelegramConfigError(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env. "
            "Run scripts/setup_telegram.py to bootstrap."
        )
    return token, chat_id


def _format_caption(draft: dict) -> str:
    """Build a Telegram caption from the draft. Telegram limit is 1024 chars."""
    title = draft.get("youtube_title", draft.get("news", "(untitled)"))
    hook = draft.get("hook", "")
    insight = draft.get("insight", "")
    takeaway = draft.get("takeaway", "")
    text = (
        f"*{title}*\n\n"
        f"*Hook:* {hook}\n"
        f"*Insight:* {insight}\n"
        f"*Takeaway:* {takeaway}"
    )
    if len(text) > 1000:
        text = text[:997] + "..."
    return text


def _inline_keyboard(job_id: str) -> dict:
    return {
        "inline_keyboard": [[
            {"text": "✅ Approve",  "callback_data": f"approve:{job_id}"},
            {"text": "❌ Reject",   "callback_data": f"reject:{job_id}"},
            {"text": "🔁 Regen",    "callback_data": f"regen:{job_id}"},
        ]]
    }


def send_for_approval(video_path: Path, draft: dict) -> dict:
    """Upload the rendered video to Telegram with inline action buttons.

    Returns the Telegram message dict on success. Raises on transport error.
    """
    import json as _json

    token, chat_id = _get_config()
    job_id = str(draft.get("job_id", "unknown"))

    with open(video_path, "rb") as f:
        files = {"video": (video_path.name, f, "video/mp4")}
        data = {
            "chat_id": chat_id,
            "caption": _format_caption(draft),
            "parse_mode": "Markdown",
            "reply_markup": _json.dumps(_inline_keyboard(job_id)),
            "supports_streaming": "true",
        }
        r = requests.post(
            f"{API_BASE}{token}/sendVideo",
            data=data, files=files, timeout=SEND_VIDEO_TIMEOUT,
        )
    if r.status_code != 200:
        raise RuntimeError(f"Telegram sendVideo {r.status_code}: {r.text[:300]}")
    body = r.json()
    if not body.get("ok"):
        raise RuntimeError(f"Telegram sendVideo error: {body}")
    return body["result"]


def _answer_callback(token: str, callback_id: str, text: str = "") -> None:
    requests.post(
        f"{API_BASE}{token}/answerCallbackQuery",
        json={"callback_query_id": callback_id, "text": text},
        timeout=15,
    )


def wait_for_decision(job_id: str, *, timeout: int = DEFAULT_APPROVAL_TIMEOUT) -> str:
    """Poll Telegram until the matching job_id callback arrives or timeout.

    Returns one of: "approve" | "reject" | "regen" | "timeout".
    """
    token, _ = _get_config()
    deadline = time.time() + timeout
    offset = 0  # request all undelivered updates

    while time.time() < deadline:
        try:
            r = requests.get(
                f"{API_BASE}{token}/getUpdates",
                params={"offset": offset, "timeout": 25, "allowed_updates": "callback_query"},
                timeout=30,
            )
        except requests.RequestException:
            time.sleep(POLL_INTERVAL)
            continue

        if r.status_code != 200:
            time.sleep(POLL_INTERVAL)
            continue

        body = r.json()
        if not body.get("ok"):
            time.sleep(POLL_INTERVAL)
            continue

        for update in body.get("result", []):
            offset = update["update_id"] + 1
            cb = update.get("callback_query")
            if not cb:
                continue
            data = cb.get("data", "")
            if ":" not in data:
                continue
            action, cb_job = data.split(":", 1)
            if cb_job != job_id:
                continue
            _answer_callback(token, cb["id"], f"Got: {action}")
            return action

        time.sleep(POLL_INTERVAL)

    return "timeout"
