"""Prompt composer — injects per-client CHANNEL_DNA + CONTENT_LAW + PROMPT_LAW.

The DNA injection is the moat. Without it, the model drifts toward generic
content within 50 generations. With it, every script inherits the active
client's tone, forbidden patterns, and quality bar.
"""

from . import client_config


def compose(task_prompt: str, *, client_name: str | None = None) -> str:
    """Wrap a task prompt with the active client's editorial guardrails.

    Order matters: DNA first (identity), then CONTENT_LAW (quality bar),
    then PROMPT_LAW (output discipline), then the task itself last so the
    model's most recent attention is on the actual instruction.

    Args:
        task_prompt: the bare task instruction.
        client_name: optional client override; defaults to env-active client.
    """
    cfg = client_config.load(client_name)
    dna = cfg.dna
    structure = " → ".join(dna.get("script_structure", []))
    allowed = ", ".join(dna.get("allowed_topics", ["any"]))
    forbidden = ", ".join(dna.get("forbidden", []))

    return f"""# CHANNEL DNA
You are writing for "{dna.get('channel_name', cfg.name)}".
Tone: {dna.get('tone', '')}.
Voice style: {dna.get('voice_style', '')}.
Hook style: {dna.get('hook_style', '')}.
Visual style: {dna.get('visual_style', '')}.
Allowed topics: {allowed}.
Forbidden: {forbidden}.
Script structure: {structure}.

# CONTENT_LAW (mandatory quality rules)
{cfg.content_law}

# PROMPT_LAW (mandatory output discipline)
{cfg.prompt_law}

# TASK
{task_prompt}

Remember: Content quality > speed. Output STRICT JSON only — no prose, no markdown fences, no commentary."""
