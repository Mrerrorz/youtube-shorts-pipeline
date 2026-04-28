"""Bootstrap helper for the Silent Capital Telegram approval bot.

Usage:
  1. Create a bot via @BotFather on Telegram. Copy the token.
  2. Send /start to your new bot.
  3. Add `TELEGRAM_BOT_TOKEN=...` to .env (only the token for now).
  4. Run this script — it polls getUpdates and prints your chat_id.
  5. Add `TELEGRAM_CHAT_ID=...` to .env.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

import requests  # noqa: E402


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
        print("  1. Open Telegram → search @BotFather → /newbot")
        print("  2. Copy the bot token into .env: TELEGRAM_BOT_TOKEN=...")
        print("  3. Send /start to your new bot from your personal Telegram.")
        print("  4. Re-run this script.")
        return 1

    print("Polling Telegram for your chat_id (send any message to your bot now)...")
    r = requests.get(
        f"https://api.telegram.org/bot{token}/getUpdates",
        params={"timeout": 30},
        timeout=35,
    )
    if r.status_code != 200:
        print(f"ERROR: Telegram getUpdates {r.status_code}: {r.text[:300]}")
        return 1

    body = r.json()
    if not body.get("ok"):
        print(f"ERROR: Telegram getUpdates: {body}")
        return 1

    updates = body.get("result", [])
    if not updates:
        print("No messages found yet. Send /start to your bot, then re-run.")
        return 1

    seen: dict[int, str] = {}
    for upd in updates:
        msg = upd.get("message") or upd.get("edited_message") or {}
        chat = msg.get("chat", {})
        cid = chat.get("id")
        if cid is None:
            continue
        name = chat.get("username") or chat.get("first_name") or chat.get("title") or "(unknown)"
        seen[cid] = name

    if not seen:
        print("No chat messages yet. Send /start to your bot, then re-run.")
        return 1

    print("\nFound chats:")
    for cid, name in seen.items():
        print(f"  chat_id={cid}  user={name}")

    print("\nAdd this to .env:")
    cid = next(iter(seen))
    print(f"TELEGRAM_CHAT_ID={cid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
