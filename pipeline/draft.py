"""Silent Capital script generation via OpenRouter + prompt composer.

Replaces the original Anthropic-direct path. Every LLM call inherits
CHANNEL_DNA + CONTENT_LAW + PROMPT_LAW through silent_capital.prompt_composer.
"""

from pathlib import Path

from .log import log
from silent_capital.openrouter_client import call_json
from silent_capital.prompt_composer import compose

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text()


def generate_draft(news: str, channel_context: str = "") -> dict:
    """Generate a Silent Capital script from a headline/news topic.

    Skips live web research (the original `research.py` path). For Silent
    Capital v1, headlines are curated by the founder, so live research
    introduces noise. Re-enable in Phase 7 once we have analytics signal.

    Returns a dict matching the schema downstream produce/upload expects:
      script, broll_prompts, youtube_title, youtube_description,
      youtube_tags, instagram_caption, thumbnail_prompt
    Plus Silent Capital extras: hook, insight, mechanism, takeaway.
    """
    log(f"Generating Silent Capital script for: {news}")

    task = _load_prompt("script_prompt.txt").format(headline=news)
    full_prompt = compose(task)

    draft = call_json(full_prompt, max_tokens=2000, temperature=0.7)

    expected_str = [
        "hook", "pivot_line", "mechanism", "takeaway", "script",
        "youtube_title", "youtube_description", "youtube_tags",
        "instagram_caption", "thumbnail_prompt",
    ]
    for field in expected_str:
        if field in draft and not isinstance(draft[field], str):
            draft[field] = str(draft[field])

    if not isinstance(draft.get("broll_prompts"), list):
        draft["broll_prompts"] = ["realistic shopping scene"] * 8
    else:
        draft["broll_prompts"] = [str(p) for p in draft["broll_prompts"][:8]]
        while len(draft["broll_prompts"]) < 8:
            draft["broll_prompts"].append("realistic business scene")

    draft["news"] = news
    draft["channel"] = "Silent Capital"
    return draft
