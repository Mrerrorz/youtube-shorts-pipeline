"""Prompt composer — injects CHANNEL_DNA + CONTENT_LAW + PROMPT_LAW before every LLM call.

The DNA injection is the moat. Without it, the model drifts toward generic finance
content within 50 generations. With it, every script inherits Silent Capital's tone,
forbidden patterns, and quality bar.
"""

import json
from functools import lru_cache
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@lru_cache(maxsize=1)
def _load_dna() -> dict:
    return json.loads((CONFIG_DIR / "CHANNEL_DNA.json").read_text())


@lru_cache(maxsize=1)
def _load_content_law() -> str:
    return (CONFIG_DIR / "CONTENT_LAW.md").read_text()


@lru_cache(maxsize=1)
def _load_prompt_law() -> str:
    return (CONFIG_DIR / "PROMPT_LAW.md").read_text()


def compose(task_prompt: str) -> str:
    """Wrap a task prompt with Silent Capital's editorial guardrails.

    Order matters: DNA first (identity), then CONTENT_LAW (quality bar),
    then PROMPT_LAW (output discipline), then the task itself last so the
    model's most recent attention is on the actual instruction.
    """
    dna = _load_dna()
    return f"""# CHANNEL DNA
You are writing for "{dna['channel_name']}".
Tone: {dna['tone']}.
Voice style: {dna['voice_style']}.
Hook style: {dna['hook_style']}.
Visual style: {dna['visual_style']}.
Allowed topics: {', '.join(dna['allowed_topics'])}.
Forbidden: {', '.join(dna['forbidden'])}.
Script structure: {' → '.join(dna['script_structure'])}.

# CONTENT_LAW (mandatory quality rules)
{_load_content_law()}

# PROMPT_LAW (mandatory output discipline)
{_load_prompt_law()}

# TASK
{task_prompt}

Remember: Content quality > speed. Output STRICT JSON only — no prose, no markdown fences, no commentary."""
