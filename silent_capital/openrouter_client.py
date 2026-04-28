"""OpenRouter client — JSON-mode enforced, retries on malformed output.

Uses OpenRouter so we can A/B different models cheaply. Default is Claude Sonnet
4.6 (best tone for psychology scripts); switch via SILENT_CAPITAL_MODEL env var.
"""

import json
import os
import time
from typing import Any

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("SILENT_CAPITAL_MODEL", "anthropic/claude-sonnet-4.5")


class OpenRouterError(RuntimeError):
    pass


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    return raw


def call_json(
    prompt: str,
    *,
    model: str | None = None,
    max_tokens: int = 1500,
    temperature: float = 0.7,
    max_retries: int = 3,
) -> dict[str, Any]:
    """POST to OpenRouter, force JSON output, retry on malformed.

    PROMPT_LAW says: if malformed, retry. So we do up to max_retries before raising.
    Each retry uses a slightly higher temperature to break out of bad patterns.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise OpenRouterError(
            "OPENROUTER_API_KEY not set. Add it to .env at the repo root."
        )

    model = model or DEFAULT_MODEL
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Mrerrorz/youtube-shorts-pipeline",
        "X-Title": "Silent Capital Engine",
    }

    last_error: str = ""
    for attempt in range(max_retries):
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": min(temperature + 0.1 * attempt, 1.0),
            "response_format": {"type": "json_object"},
        }
        try:
            r = requests.post(OPENROUTER_URL, json=body, headers=headers, timeout=120)
        except requests.RequestException as e:
            last_error = f"network: {e}"
            time.sleep(2 ** attempt)
            continue

        if r.status_code != 200:
            last_error = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            raise OpenRouterError(last_error)

        try:
            data = r.json()
            raw = data["choices"][0]["message"]["content"]
        except (KeyError, ValueError) as e:
            last_error = f"unexpected response shape: {e}"
            time.sleep(2 ** attempt)
            continue

        try:
            return json.loads(_strip_fences(raw))
        except json.JSONDecodeError as e:
            last_error = f"JSON parse failed (attempt {attempt + 1}): {e}; raw={raw[:200]!r}"
            continue

    raise OpenRouterError(f"OpenRouter failed after {max_retries} retries. Last: {last_error}")
