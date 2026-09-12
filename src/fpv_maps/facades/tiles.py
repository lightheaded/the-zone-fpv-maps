"""Fetch one Fotoladu frame as an image, from the Deep Zoom tiles of the viewer.

The service has no bulk download. The viewer serves each frame as Deep Zoom tiles,
and this module stitches the tiles of one level back into one image. It caches every
tile under ``data/fotoladu`` so that a rebuild costs no request, and it rate limits
itself. See docs/licensing.md D6: the project must ask for bulk access before it uses
this at any scale. This is proof of concept volume only.
"""

from __future__ import annotations

import math
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from fpv_maps.facades.fotoladu import Photo

TILE = 256
UA = "the-zone-fpv-maps/0.4 (map pipeline, proof of concept; GitHub lightheaded)"
_RATE = threading.Semaphore(4)
_last = [0.0]
_lock = threading.Lock()
MIN_INTERVAL = 0.06  # about 16 requests a second at most, over 4 workers


def level_for(photo: Photo, level: int | None = None) -> int:
    """Deep Zoom level that holds the full frame, or a smaller one."""
    full = math.ceil(math.log2(max(photo.width, photo.height)))
    return full if level is None else min(level, full)


def level_size(photo: Photo, level: int) -> tuple[int, int]:
    full = math.ceil(math.log2(max(photo.width, photo.height)))
    s = 2 ** (full - level)
    return max(1, math.ceil(photo.width / s)), max(1, math.ceil(photo.height / s))


def _throttle() -> None:
    with _lock:
        wait = MIN_INTERVAL - (time.monotonic() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()


def _get_tile(photo: Photo, level: int, col: int, row: int, cache: Path) -> Path | None:
    p = cache / photo.image / str(level) / f"{col}_{row}.jpg"
    if p.exists():
        return p if p.stat().st_size > 0 else None
    p.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(photo.tile_url(level, col, row), headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with _RATE:
                _throttle()
                with urllib.request.urlopen(req, timeout=45) as fh:
                    ctype = fh.headers.get("Content-Type", "")
                    data = fh.read()
            if "jpeg" not in ctype:  # a PNG here is the out-of-range placeholder
                p.write_bytes(b"")
                return None
            p.write_bytes(data)
            return p
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 2:
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def fetch_frame(
    photo: Photo,
    cache: Path,
    level: int | None = None,
    box: tuple[int, int, int, int] | None = None,
    workers: int = 4,
) -> tuple[Image.Image, tuple[int, int], int]:
    """Stitch one frame. ``box`` limits the fetch to a pixel rectangle of that level.

    Returns the image, its (x, y) offset inside the level, and the number of tiles
    fetched or read from cache.
    """
    lv = level_for(photo, level)
    w, h = level_size(photo, lv)
    x0, y0, x1, y1 = box if box else (0, 0, w, h)
    x0 = max(0, min(x0, w))
    y0 = max(0, min(y0, h))
    x1 = max(x0 + 1, min(x1, w))
    y1 = max(y0 + 1, min(y1, h))
    c0, r0 = x0 // TILE, y0 // TILE
    c1, r1 = (x1 - 1) // TILE, (y1 - 1) // TILE
    jobs = [(c, r) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
    out = Image.new("RGB", ((c1 - c0 + 1) * TILE, (r1 - r0 + 1) * TILE), (0, 0, 0))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        paths = list(pool.map(lambda cr: _get_tile(photo, lv, cr[0], cr[1], cache), jobs))
    got = 0
    for (c, r), p in zip(jobs, paths, strict=True):
        if p is None:
            continue
        got += 1
        with Image.open(p) as im:
            out.paste(im.convert("RGB"), ((c - c0) * TILE, (r - r0) * TILE))
    return out, (c0 * TILE, r0 * TILE), got
