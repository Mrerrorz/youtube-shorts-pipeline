"""Scene builder — bridges script JSON → renderable scene plan.

The PRD calls this the critical custom module. It turns a finished script into
a list of scenes the visual fetcher (Phase 4) can hydrate with stock footage.
Each scene knows its duration, visual intent, on-screen caption, and emotion.
"""

from .openrouter_client import call_json
from .prompt_composer import compose

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text()


VALID_EMOTIONS = {"curiosity", "tension", "recognition", "discomfort", "resolution"}


def build_scenes(draft: dict) -> list[dict]:
    """Given a Silent Capital draft, return a normalized list of scenes.

    Each scene: {scene, duration, visual_query, caption, emotion}.
    Total duration is clamped to 60-80s. Invalid emotions snap to 'curiosity'.
    """
    task = _load_prompt("scene_prompt.txt").format(
        script=draft["script"],
        headline=draft.get("news", ""),
        hook=draft.get("hook", ""),
        insight=draft.get("insight", ""),
        mechanism=draft.get("mechanism", ""),
        takeaway=draft.get("takeaway", ""),
    )
    full_prompt = compose(task)

    result = call_json(full_prompt, max_tokens=1500, temperature=0.6)
    raw_scenes = result.get("scenes", [])
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise ValueError(f"scene_builder: invalid scenes payload: {result!r}")

    scenes: list[dict] = []
    for i, s in enumerate(raw_scenes, start=1):
        duration = float(s.get("duration", 8))
        duration = max(4.0, min(15.0, duration))
        emotion = str(s.get("emotion", "curiosity")).lower().strip()
        if emotion not in VALID_EMOTIONS:
            emotion = "curiosity"
        scenes.append({
            "scene": i,
            "duration": duration,
            "visual_query": str(s.get("visual_query", "")).strip(),
            "caption": str(s.get("caption", "")).strip(),
            "emotion": emotion,
        })

    total = sum(s["duration"] for s in scenes)
    if total < 60 or total > 80:
        scale = max(60.0, min(80.0, total)) / total
        for s in scenes:
            s["duration"] = round(s["duration"] * scale, 2)

    return scenes
