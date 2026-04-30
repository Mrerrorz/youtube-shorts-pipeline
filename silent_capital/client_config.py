"""Per-client configuration loader.

Each client has a folder under `clients/<name>/` containing their brand DNA,
content laws, voice ID, music tracks, caption style, and optional prompt
overrides. The loader merges client-specific config with shared defaults so
every client gets a complete config without duplicating the common parts.

Layout:
  clients/
    shared/                       # default fallbacks for everything
      CHANNEL_DNA.json
      CONTENT_LAW.md
      PROMPT_LAW.md
      caption_style.json
      music/
      prompts/
        script_prompt.txt
        scene_prompt.txt
    <client_name>/
      CHANNEL_DNA.json            # required — overrides shared
      CONTENT_LAW.md              # optional — falls back to shared
      voice_id.txt                # optional — falls back to env VOICE_ID_EN
      caption_style.json          # optional — falls back to shared default
      music/                      # optional — falls back to shared/music
      prompts/                    # optional — falls back to shared/prompts
        script_prompt.txt
        scene_prompt.txt

The active client is selected via:
  1. CLI arg `--client <name>`
  2. env var `SILENT_CAPITAL_CLIENT`
  3. defaults to `silent_capital` (the founder's own brand)
"""

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENTS_ROOT = REPO_ROOT / "clients"
SHARED_DIR = CLIENTS_ROOT / "shared"

DEFAULT_CLIENT = "silent_capital"


@dataclass(frozen=True)
class ClientConfig:
    """Resolved per-client configuration.

    All paths point to the right file (client-specific if it exists,
    shared default otherwise). Strings/dicts are loaded values.
    """
    name: str
    dna: dict                     # CHANNEL_DNA.json contents
    content_law: str              # CONTENT_LAW.md contents
    prompt_law: str               # PROMPT_LAW.md contents
    voice_id: str                 # ElevenLabs voice ID
    caption_style: dict           # font, size, color, position
    music_dir: Path               # folder of MP3s for this client
    script_prompt_path: Path      # client-specific or shared
    scene_prompt_path: Path
    output_dir: Path              # where this client's renders land


def get_active_client() -> str:
    """Return the active client name from CLI/env, or the default."""
    return os.environ.get("SILENT_CAPITAL_CLIENT", DEFAULT_CLIENT).strip() or DEFAULT_CLIENT


def _resolve_path(client_dir: Path, relative: str) -> Path:
    """Look up a file in client dir, fall back to shared dir.

    Raises if the file doesn't exist in either place.
    """
    client_path = client_dir / relative
    if client_path.exists():
        return client_path
    shared_path = SHARED_DIR / relative
    if shared_path.exists():
        return shared_path
    raise FileNotFoundError(
        f"Config file '{relative}' not found in client '{client_dir.name}' or shared/"
    )


def _resolve_dir(client_dir: Path, relative: str) -> Path:
    """Look up a directory in client dir, fall back to shared dir.

    Returns the first existing one. If neither exists, returns the client
    path (so it can be created lazily by the caller).
    """
    client_path = client_dir / relative
    if client_path.exists() and client_path.is_dir():
        return client_path
    shared_path = SHARED_DIR / relative
    if shared_path.exists() and shared_path.is_dir():
        return shared_path
    return client_path


@lru_cache(maxsize=8)
def load(client_name: str | None = None) -> ClientConfig:
    """Load and cache a client's resolved config.

    If client_name is None, uses the active-client env var.
    """
    name = (client_name or get_active_client()).strip()
    client_dir = CLIENTS_ROOT / name
    if not client_dir.exists():
        raise FileNotFoundError(
            f"Client '{name}' not found at {client_dir}. "
            f"Create it with: cp -r clients/shared clients/{name} "
            f"and customize CHANNEL_DNA.json."
        )

    dna_path = _resolve_path(client_dir, "CHANNEL_DNA.json")
    dna = json.loads(dna_path.read_text())

    content_law_path = _resolve_path(client_dir, "CONTENT_LAW.md")
    prompt_law_path = _resolve_path(client_dir, "PROMPT_LAW.md")

    voice_path = client_dir / "voice_id.txt"
    if voice_path.exists():
        voice_id = voice_path.read_text().strip()
    else:
        voice_id = os.environ.get("VOICE_ID_EN", "JBFqnCBsd6RMkjVDRZzb")  # George default

    style_path = client_dir / "caption_style.json"
    if not style_path.exists():
        style_path = SHARED_DIR / "caption_style.json"
    if style_path.exists():
        caption_style = json.loads(style_path.read_text())
    else:
        caption_style = _DEFAULT_CAPTION_STYLE

    music_dir = _resolve_dir(client_dir, "music")
    script_prompt = _resolve_path(client_dir, "prompts/script_prompt.txt")
    scene_prompt = _resolve_path(client_dir, "prompts/scene_prompt.txt")

    output_dir = Path.home() / ".youtube-shorts-pipeline" / "clients" / name
    output_dir.mkdir(parents=True, exist_ok=True)

    return ClientConfig(
        name=name,
        dna=dna,
        content_law=content_law_path.read_text(),
        prompt_law=prompt_law_path.read_text(),
        voice_id=voice_id,
        caption_style=caption_style,
        music_dir=music_dir,
        script_prompt_path=script_prompt,
        scene_prompt_path=scene_prompt,
        output_dir=output_dir,
    )


_DEFAULT_CAPTION_STYLE = {
    "fontname": "Helvetica Neue",
    "fontsize": 96,
    "primary_color_bgr": "&H00FFFFFF",   # white
    "highlight_color_bgr": "&H0000FFFF",  # yellow (for word highlight)
    "outline_color_bgr": "&H00000000",   # black outline
    "outline_width": 6,
    "shadow_depth": 2,
    "alignment": 2,                      # bottom-center
    "margin_v_pct": 0.32,                # 32% from bottom
    "margin_h": 60,
    "bold": True,
}


def list_clients() -> list[str]:
    """List all known client names (excluding 'shared')."""
    if not CLIENTS_ROOT.exists():
        return []
    return sorted(
        d.name for d in CLIENTS_ROOT.iterdir()
        if d.is_dir() and d.name != "shared"
    )
