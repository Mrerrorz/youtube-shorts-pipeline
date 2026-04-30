"""Script generation via OpenRouter + per-client prompt composer.

Each draft inherits the active client's CHANNEL_DNA + CONTENT_LAW +
PROMPT_LAW through silent_capital.prompt_composer. The script template
itself is also client-overridable (clients/<name>/prompts/script_prompt.txt).
"""

from .log import log
from silent_capital import client_config
from silent_capital.openrouter_client import call_json
from silent_capital.prompt_composer import compose


def generate_draft(news: str, channel_context: str = "", *, client_name: str | None = None) -> dict:
    """Generate a script from a headline for the active (or specified) client.

    Returns a dict matching the schema downstream produce/upload expects:
      script, broll_prompts, youtube_title, youtube_description,
      youtube_tags, instagram_caption, thumbnail_prompt
    Plus structural extras: hook, pivot_line, mechanism, takeaway.
    """
    cfg = client_config.load(client_name)
    log(f"Generating script for [{cfg.name}]: {news}")

    task = cfg.script_prompt_path.read_text().format(headline=news)
    full_prompt = compose(task, client_name=cfg.name)

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
    draft["client"] = cfg.name
    draft["channel"] = cfg.dna.get("channel_name", cfg.name)
    return draft
