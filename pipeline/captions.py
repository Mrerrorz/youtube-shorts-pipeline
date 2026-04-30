"""Whisper word-level timestamps + ASS subtitle generation + Pillow fallback."""

from pathlib import Path

from .log import log


def _has_ass_filter() -> bool:
    """Check if ffmpeg has libass (for ASS subtitle burn-in)."""
    import subprocess
    try:
        r = subprocess.run(
            ["ffmpeg", "-filters"],
            capture_output=True, text=True, timeout=5,
        )
        return "ass" in r.stdout
    except Exception:
        return False


def _whisper_word_timestamps(audio_path: Path, lang: str = "en") -> list[dict]:
    """Get word-level timestamps from Whisper.

    Returns list of {"word": str, "start": float, "end": float}.
    """
    try:
        import whisper
    except ImportError:
        log("Whisper not installed — skipping word timestamps")
        return []

    log("Running Whisper for word-level timestamps...")
    model = whisper.load_model("base")
    result = model.transcribe(
        str(audio_path),
        language=lang[:2],
        word_timestamps=True,
    )

    words = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            words.append({
                "word": w["word"].strip(),
                "start": w["start"],
                "end": w["end"],
            })

    log(f"Got {len(words)} word timestamps.")
    return words


def _group_words(words: list[dict], group_size: int = 4) -> list[list[dict]]:
    """Group words into chunks of group_size for caption display."""
    groups = []
    for i in range(0, len(words), group_size):
        groups.append(words[i:i + group_size])
    return groups


def _format_ass_time(seconds: float) -> str:
    """Format seconds to ASS timestamp: H:MM:SS.cc (centiseconds)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _generate_ass(words: list[dict], output_path: Path, video_width: int = 1080, video_height: int = 1920, *, style: dict | None = None):
    """Generate ASS subtitle file with per-client style + word highlighting.

    Style dict (from clients/<name>/caption_style.json) controls font, size,
    colors, outline, alignment, position. Falls back to defaults if absent.
    """
    if style is None:
        try:
            from silent_capital import client_config
            style = client_config.load().caption_style
        except Exception:
            style = {}

    fontname = style.get("fontname", "Helvetica Neue")
    fontsize = int(style.get("fontsize", 96))
    primary = style.get("primary_color_bgr", "&H00FFFFFF")
    highlight = style.get("highlight_color_bgr", "&H0000FFFF")
    outline_color = style.get("outline_color_bgr", "&H00000000")
    outline_width = int(style.get("outline_width", 6))
    shadow = int(style.get("shadow_depth", 2))
    alignment = int(style.get("alignment", 2))
    margin_v_pct = float(style.get("margin_v_pct", 0.32))
    margin_h = int(style.get("margin_h", 60))
    bold_flag = -1 if style.get("bold", True) else 0

    margin_v = int(video_height * margin_v_pct)
    highlight_fs = int(fontsize * 0.83)  # active-word slightly smaller for visual punch

    header = f"""[Script Info]
Title: Pipeline Captions
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{fontname},{fontsize},{primary},{highlight},{outline_color},&H80000000,{bold_flag},0,0,0,100,100,0,0,1,{outline_width},{shadow},{alignment},{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    groups = _group_words(words)
    events = []

    # ASS uses BGR with leading &H... — extract just the color portion for inline overrides
    highlight_inline = highlight.replace("&H00", "").replace("&H", "")

    for group in groups:
        if not group:
            continue

        for active_idx, active_word in enumerate(group):
            start = active_word["start"]
            end = active_word["end"]

            parts = []
            for j, w in enumerate(group):
                if j == active_idx:
                    parts.append(f"{{\\c&H{highlight_inline}&\\b1\\fs{highlight_fs}}}{w['word']}{{\\r}}")
                else:
                    parts.append(w["word"])

            text = " ".join(parts)
            events.append(
                f"Dialogue: 0,{_format_ass_time(start)},{_format_ass_time(end)},Default,,0,0,0,,{text}"
            )

    output_path.write_text(header + "\n".join(events), encoding="utf-8")
    log(f"ASS captions saved: {output_path.name}")
    return output_path


def _generate_srt(words: list[dict], output_path: Path) -> Path:
    """Generate standard SRT file from word timestamps."""
    groups = _group_words(words)
    lines = []

    for i, group in enumerate(groups, 1):
        if not group:
            continue
        start = group[0]["start"]
        end = group[-1]["end"]
        text = " ".join(w["word"] for w in group)

        start_ts = _srt_time(start)
        end_ts = _srt_time(end)
        lines.append(f"{i}\n{start_ts} --> {end_ts}\n{text}\n")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    log(f"SRT captions saved: {output_path.name}")
    return output_path


def _srt_time(seconds: float) -> str:
    """Format seconds to SRT timestamp: HH:MM:SS,mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_captions(audio_path: Path, work_dir: Path, lang: str = "en", *, client_name: str | None = None) -> dict:
    """Generate captions: ASS (for burn-in) + SRT (for YouTube upload).

    Returns dict with keys: srt_path, ass_path, words (for music ducking).
    Caption style is loaded from the active client's config.
    """
    try:
        from silent_capital import client_config
        style = client_config.load(client_name).caption_style
    except Exception:
        style = None

    words = _whisper_word_timestamps(audio_path, lang)

    result = {"words": words}

    if not words:
        log("No word timestamps — skipping caption generation")
        # Fallback: run whisper CLI for SRT only
        try:
            from .config import run_cmd
            run_cmd([
                "whisper", str(audio_path),
                "--model", "base",
                "--language", lang[:2],
                "--output_format", "srt",
                "--output_dir", str(work_dir),
            ], capture=True)
            candidates = list(work_dir.glob("*.srt"))
            if candidates:
                srt = candidates[0]
                final = audio_path.with_suffix(".srt")
                srt.rename(final)
                result["srt_path"] = str(final)
        except Exception as e:
            log(f"Whisper CLI fallback failed: {e}")
        return result

    # Generate SRT
    srt_path = work_dir / f"captions_{lang}.srt"
    _generate_srt(words, srt_path)
    result["srt_path"] = str(srt_path)

    # Generate ASS for burn-in
    ass_path = work_dir / f"captions_{lang}.ass"
    _generate_ass(words, ass_path, style=style)
    result["ass_path"] = str(ass_path)

    return result
