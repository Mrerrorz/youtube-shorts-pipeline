"""B-roll fetcher with prioritized fallback: Pexels Video → Pexels Photo → Gemini Imagen → solid color.

Returns a list of source assets (mixed .mp4 videos and .png images). Downstream
assemble.py inspects each file's extension to decide how to process it (videos
get trimmed/scaled; images get Ken Burns animation).

This is the quality jump for client deliverables: real motion footage instead
of animated stills wherever Pexels has a matching clip.
"""

import base64
from pathlib import Path

import requests
from PIL import Image

from .config import VIDEO_WIDTH, VIDEO_HEIGHT, get_gemini_key, run_cmd
from .log import log
from .retry import with_retry
from silent_capital.visual_fetcher import fetch_pexels_photo, fetch_pexels_video


@with_retry(max_retries=3, base_delay=2.0)
def _generate_image_gemini(prompt: str, output_path: Path, api_key: str):
    """Generate image via Gemini native image generation (final fallback)."""
    url = (
        "https://generativelanguage.googleapis.com/v1beta"
        "/models/gemini-2.0-flash-exp-image-generation:generateContent"
    )
    body = {
        "contents": [{"parts": [{"text": f"Generate an image: {prompt}"}]}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
    }
    r = requests.post(
        url, json=body, timeout=90,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    if r.status_code != 200:
        try:
            detail = r.json().get("error", {}).get("message", r.text[:200])
        except Exception:
            detail = r.text[:200]
        raise RuntimeError(f"Gemini API {r.status_code}: {detail}")
    data = r.json()
    for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        if "inlineData" in part:
            img_b64 = part["inlineData"]["data"]
            output_path.write_bytes(base64.b64decode(img_b64))
            return
    raise RuntimeError("No image in Gemini response")


def _fallback_frame(i: int, out_dir: Path) -> Path:
    """Solid colour fallback frame if everything else fails."""
    colors = [(20, 20, 60), (40, 10, 40), (10, 30, 50)]
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), colors[i % len(colors)])
    path = out_dir / f"broll_{i}.png"
    img.save(path)
    return path


def _process_pexels_image(out_path: Path) -> None:
    """Resize/crop a downloaded Pexels image to 1080x1920."""
    img = Image.open(out_path).convert("RGB")
    target_w, target_h = VIDEO_WIDTH, VIDEO_HEIGHT
    orig_w, orig_h = img.size
    scale = max(target_w / orig_w, target_h / orig_h)
    new_w, new_h = int(orig_w * scale), int(orig_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))
    img.save(out_path)


def generate_broll(prompts: list, out_dir: Path) -> list[Path]:
    """For each prompt, fetch the best available asset.

    Priority per prompt:
      1. Pexels portrait VIDEO  → broll_N.mp4
      2. Pexels portrait PHOTO  → broll_N.png
      3. Gemini Imagen          → broll_N.png
      4. Solid color fallback   → broll_N.png

    Returns list of Path. assemble.py inspects each suffix to handle videos
    (trim+scale) vs images (Ken Burns animation).
    """
    api_key = ""
    assets: list[Path] = []

    n = len(prompts) or 1
    for i, prompt in enumerate(prompts):
        # Try video first
        video_path = out_dir / f"broll_{i}.mp4"
        log(f"Frame {i+1}/{n}: searching Pexels VIDEO for '{prompt}'...")
        if fetch_pexels_video(prompt, video_path, log_fn=log):
            assets.append(video_path)
            continue

        # Fallback to Pexels photo
        image_path = out_dir / f"broll_{i}.png"
        log(f"Frame {i+1}/{n}: no video, trying Pexels PHOTO...")
        if fetch_pexels_photo(prompt, image_path, log_fn=log):
            assets.append(image_path)
            continue

        # Fallback to Gemini Imagen
        log(f"Frame {i+1}/{n}: falling back to Gemini Imagen...")
        try:
            if not api_key:
                api_key = get_gemini_key()
            _generate_image_gemini(prompt, image_path, api_key)
            _process_pexels_image(image_path)  # Imagen output also needs resize
            assets.append(image_path)
        except Exception as e:
            log(f"Frame {i+1}: Imagen failed ({e}) — solid-color fallback")
            assets.append(_fallback_frame(i, out_dir))

    return assets


def animate_frame(img_path: Path, out_path: Path, duration: float, effect: str = "zoom_in"):
    """Ken Burns animation on a single still image. Used for image-source clips."""
    fps = 30
    frames = int(duration * fps)
    w, h = VIDEO_WIDTH, VIDEO_HEIGHT

    if effect == "zoom_in":
        vf = (
            f"scale={int(w * 1.12)}:{int(h * 1.12)},"
            f"zoompan=z='1.12-0.12*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={w}x{h}:fps={fps}"
        )
    elif effect == "pan_right":
        vf = (
            f"scale={int(w * 1.15)}:{int(h * 1.15)},"
            f"zoompan=z=1.15:x='0.15*iw*on/{frames}':y='ih*0.075'"
            f":d={frames}:s={w}x{h}:fps={fps}"
        )
    else:  # zoom_out
        vf = (
            f"scale={int(w * 1.12)}:{int(h * 1.12)},"
            f"zoompan=z='1.0+0.12*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={w}x{h}:fps={fps}"
        )

    run_cmd([
        "ffmpeg", "-loop", "1", "-i", str(img_path),
        "-vf", vf, "-t", str(duration), "-r", str(fps),
        "-pix_fmt", "yuv420p", str(out_path), "-y", "-loglevel", "quiet",
    ])


def trim_video_clip(src_path: Path, out_path: Path, duration: float):
    """Trim a Pexels video clip to target duration, scale-pad to 1080x1920, 30fps.

    If source is shorter than `duration`, loops it. Strips audio (we use voiceover).
    """
    fps = 30
    w, h = VIDEO_WIDTH, VIDEO_HEIGHT
    # Scale to fill 1080x1920 (cropping if needed), force fps + pixel format
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},fps={fps},setsar=1"
    )
    run_cmd([
        "ffmpeg",
        "-stream_loop", "-1", "-i", str(src_path),
        "-t", f"{duration}",
        "-vf", vf,
        "-pix_fmt", "yuv420p",
        "-an",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        str(out_path), "-y", "-loglevel", "quiet",
    ])
