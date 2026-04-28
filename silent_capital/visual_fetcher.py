"""Hybrid visual fetcher — Pexels real photos primary, Gemini Imagen fallback.

For Silent Capital MVP: realistic stock photos beat AI-generated stills on a
finance channel where credibility is the moat. Pexels Photos has portrait
orientation and high-res images suitable for 1080x1920 vertical Shorts.

Contract: drop-in for the original broll.py — same input (prompt list,
output dir) and same output (list of PNG paths sized to 1080x1920).
"""

import os
from pathlib import Path

import requests
from PIL import Image

PEXELS_PHOTOS_URL = "https://api.pexels.com/v1/search"
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
