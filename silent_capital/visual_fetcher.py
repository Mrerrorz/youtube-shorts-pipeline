"""Hybrid visual fetcher — Pexels real photos + videos, Gemini Imagen fallback.

For Silent Capital and clients: real motion footage > stock photos > AI stills.
Pexels Videos API provides actual filmed portrait clips that look 5x more
cinematic than animated stills. Photos are used as fallback when no matching
video is found.

Contract: returns either a video file (.mp4) or a photo (.png) with metadata
indicating which type. Caller (broll.py) handles each type appropriately.
"""

import os
from pathlib import Path

import requests
from PIL import Image

PEXELS_PHOTOS_URL = "https://api.pexels.com/v1/search"
PEXELS_VIDEOS_URL = "https://api.pexels.com/videos/search"
TARGET_W = 1080
TARGET_H = 1920


def _resize_crop_portrait(src_path: Path, out_path: Path) -> None:
    """Resize and center-crop an image to 1080x1920 portrait."""
    img = Image.open(src_path).convert("RGB")
    orig_w, orig_h = img.size
    scale = max(TARGET_W / orig_w, TARGET_H / orig_h)
    new_w, new_h = int(orig_w * scale), int(orig_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - TARGET_W) // 2
    top = (new_h - TARGET_H) // 2
    img = img.crop((left, top, left + TARGET_W, top + TARGET_H))
    img.save(out_path)


def fetch_pexels_video(query: str, out_path: Path, *, min_duration: float = 3.0, max_duration: float = 30.0, log_fn=print) -> bool:
    """Search Pexels for a portrait video matching query, save as MP4.

    Filters: portrait orientation, duration in range, picks SD/HD variant
    closest to 1080x1920. Returns True on success, False to fall back.
    """
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        log_fn("PEXELS_API_KEY not set — skipping Pexels video")
        return False

    try:
        r = requests.get(
            PEXELS_VIDEOS_URL,
            headers={"Authorization": api_key},
            params={"query": query, "per_page": 10, "orientation": "portrait", "size": "medium"},
            timeout=30,
        )
        if r.status_code != 200:
            log_fn(f"Pexels video {r.status_code}: {r.text[:200]}")
            return False

        videos = r.json().get("videos", [])
        if not videos:
            log_fn(f"Pexels video: no portrait results for '{query}'")
            return False

        # Pick first video with duration in range
        chosen = None
        for v in videos:
            dur = v.get("duration", 0)
            if min_duration <= dur <= max_duration:
                chosen = v
                break
        if not chosen:
            chosen = videos[0]  # take whatever we got

        # Pick the best video file: prefer SD around 720p height for portrait
        # (HD often huge, SD tiny). Sort by closest to target_h, prefer .mp4
        files = chosen.get("video_files", [])
        if not files:
            log_fn(f"Pexels video: chosen result has no files")
            return False

        def _score(vf):
            h = vf.get("height", 0)
            w = vf.get("width", 0)
            # Prefer portrait (h>w) and height between 1280-1920
            portrait_bonus = 0 if h > w else 1000
            height_dist = abs(h - 1600)
            mp4_bonus = 0 if "mp4" in (vf.get("file_type") or "") else 100
            return portrait_bonus + height_dist + mp4_bonus

        files_sorted = sorted(files, key=_score)
        best = files_sorted[0]
        url = best.get("link")
        if not url:
            log_fn(f"Pexels video: no link in best file")
            return False

        # Download
        log_fn(f"Pexels video downloading: {best.get('width')}x{best.get('height')} {best.get('file_type')}")
        vid_resp = requests.get(url, timeout=120, stream=True)
        if vid_resp.status_code != 200:
            log_fn(f"Pexels video download {vid_resp.status_code}")
            return False

        with open(out_path, "wb") as f:
            for chunk in vid_resp.iter_content(chunk_size=64 * 1024):
                f.write(chunk)
        return True
    except Exception as e:
        log_fn(f"Pexels video fetch failed for '{query}': {e}")
        return False


def fetch_pexels_photo(query: str, out_path: Path, *, log_fn=print) -> bool:
    """Search Pexels for a portrait photo matching query, save as PNG.

    Returns True on success, False on any failure (caller should fall back).
    """
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        log_fn("PEXELS_API_KEY not set — skipping Pexels")
        return False

    try:
        r = requests.get(
            PEXELS_PHOTOS_URL,
            headers={"Authorization": api_key},
            params={"query": query, "per_page": 5, "orientation": "portrait"},
            timeout=30,
        )
        if r.status_code != 200:
            log_fn(f"Pexels {r.status_code}: {r.text[:200]}")
            return False
        photos = r.json().get("photos", [])
        if not photos:
            log_fn(f"Pexels: no portrait photos for '{query}'")
            return False

        photo = photos[0]
        src_url = photo["src"].get("large2x") or photo["src"].get("large") or photo["src"]["original"]
        img_resp = requests.get(src_url, timeout=60)
        if img_resp.status_code != 200:
            log_fn(f"Pexels download {img_resp.status_code}")
            return False

        tmp = out_path.with_suffix(".tmp")
        tmp.write_bytes(img_resp.content)
        try:
            _resize_crop_portrait(tmp, out_path)
        finally:
            tmp.unlink(missing_ok=True)
        return True
    except Exception as e:
        log_fn(f"Pexels fetch failed for '{query}': {e}")
        return False
