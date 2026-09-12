"""Choose the source photos and fit a camera to each one.

Photo choice is the step that decides whether a wall gets its own facade or a picture
of the road in front of it, so it is done carefully and the result is cached. The fit
is slow, the tile fetch is metered, and neither has to run twice for the same map.

The cache is JSON beside the tile cache. It holds the photo record and the camera, so
a rebuild at another texture level costs no fit and no metadata request.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from fpv_maps.facades import bake
from fpv_maps.facades.fotoladu import Camera, Photo, query, resect_candidates
from fpv_maps.facades.orthocheck import best_ordering, score
from fpv_maps.facades.tiles import fetch_frame, level_size

#: 994 px wide, 12 tiles. Enough detail to correlate a frame with the orthophoto, and
#: cheap enough to do it for every candidate photo before any of them is chosen.
SCORE_LEVEL = 10

#: The whole frame of an oblique photo is about 1 km across, so a camera that sees the
#: map box at all is fitted from corners that lie well outside it. The terrain has to
#: reach that far, or the corner heights are wrong and the camera moves with them.
TERRAIN_PAD_M = 2000.0

#: An oblique photo taken from too low or too high above the horizon gives a facade
#: either no pixels or a very oblique smear.
MIN_ELEVATION_DEG = 25.0
MAX_ELEVATION_DEG = 55.0

OCTANTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def _camera_to_json(cam: Camera) -> dict:
    return {
        "f_px": cam.f_px,
        "centre": list(map(float, cam.centre)),
        "rotation": [list(map(float, r)) for r in cam.rotation],
        "width": cam.width,
        "height": cam.height,
        "rms_px": cam.rms_px,
        "tilt_deg": cam.tilt_deg,
        "ground_z": cam.ground_z,
    }


def _camera_from_json(raw: dict) -> Camera:
    return Camera(
        f_px=raw["f_px"],
        centre=np.array(raw["centre"], float),
        rotation=np.array(raw["rotation"], float),
        width=raw["width"],
        height=raw["height"],
        rms_px=raw["rms_px"],
        tilt_deg=raw["tilt_deg"],
        ground_z=raw["ground_z"],
    )


def _photo_to_json(p: Photo) -> dict:
    return {
        "id": p.id,
        "image": p.image,
        "rada": p.rada,
        "width": p.width,
        "height": p.height,
        "corners": [list(c) for c in p.corners],
        "korgus_m": p.korgus_m,
        "date": p.date,
        "accuracy": p.accuracy,
        "tiled": p.tiled,
    }


def _photo_from_json(raw: dict) -> Photo:
    return Photo(
        id=raw["id"],
        image=raw["image"],
        rada=raw["rada"],
        width=raw["width"],
        height=raw["height"],
        corners=tuple(tuple(c) for c in raw["corners"]),
        korgus_m=raw["korgus_m"],
        date=raw["date"],
        accuracy=raw["accuracy"],
        tiled=raw["tiled"],
    )


def _candidates(bbox, log) -> list[Photo]:
    """Every usable photo over the box, from a query at five points inside it.

    The service answers for one ground point: it lists the photos that see that point.
    One query at the centre of a 1 km box therefore misses every photo that covers a
    corner and stops short of the middle. Five queries, at the centre and at the four
    quarter points, found 39 photos over the Tartu old town where the centre alone
    found 24, and the extra ones are exactly the ones that see the edges of the map.

    The filter keeps the photos that can carry a facade: accuracy 2, tiled, flown at a
    normal height, from the two newest cameras, and from 2022 or later.
    """
    quarter_e = bbox.width / 4.0
    quarter_n = bbox.height / 4.0
    east, north = bbox.center
    points = [
        (east, north),
        (east - quarter_e, north - quarter_n),
        (east + quarter_e, north - quarter_n),
        (east - quarter_e, north + quarter_n),
        (east + quarter_e, north + quarter_n),
    ]
    found: dict[str, Photo] = {}
    for e, n in points:
        for photo in query(e, n):
            if (
                photo.accuracy == 2
                and photo.tiled
                and 400 < photo.korgus_m < 3000
                and photo.camera in ("a7r3", "a7r4")
                and photo.date >= "2022"
            ):
                found.setdefault(photo.image, photo)
    out = sorted(found.values(), key=lambda p: p.date, reverse=True)
    log(f"{len(points)} metadata queries over the box found {len(out)} usable photos")
    return out


def select(
    bbox,
    origin_en: tuple[float, float],
    ground_z: float,
    corner_field,
    gc_pts: np.ndarray,
    gc_lum: np.ndarray,
    cache_dir: Path,
    max_candidates: int,
    max_sources: int,
    min_correlation: float,
    log=print,
) -> list[tuple[Photo, Camera, float]]:
    """Photos over the map with a camera that the orthophoto agrees with.

    ``corner_field`` gives the terrain height at any point, including well outside the
    map box, because the frame corners lie up to a kilometre away.
    """
    east, north = origin_en
    candidates = _candidates(bbox, log)
    log(f"candidate photos {len(candidates)}, of which {min(len(candidates), max_candidates)} used")

    kept: list[tuple[Photo, Camera, float, float, float, float]] = []
    seen: set[str] = set()
    for photo in candidates[:max_candidates]:
        if photo.image in seen:
            continue
        seen.add(photo.image)
        image, offset, _ = fetch_frame(photo, cache_dir, level=SCORE_LEVEL)
        level_w, _ = level_size(photo, SCORE_LEVEL)
        arr = np.asarray(image, np.uint8)
        scale = level_w / photo.width

        # 1. The orthophoto says which published corner is which corner of the frame.
        ranked = best_ordering(photo, arr, scale, offset, gc_pts, gc_lum)
        h_corr, rot, rev = ranked[0]

        # 2. Fit the camera with that reading only. Two height models are tried: the
        #    terrain under each corner, and one plane through their mean. The corners
        #    lie far apart, and which of the two fits better depends on the relief.
        zs = np.array([corner_field.sample_one(e, n) for e, n in photo.corners])
        cams = resect_candidates(photo, ground_z=zs, orderings=[(rot, rev)]) + resect_candidates(
            photo, ground_z=float(zs.mean()), orderings=[(rot, rev)]
        )
        if not cams:
            log(f"  {photo.date} {photo.image[-7:]}  no camera fits the chosen ordering")
            continue

        # 3. Score the fitted cameras the same way and keep the best.
        corr, cam = max(
            ((score(c, arr, scale, offset, gc_pts, gc_lum)[0], c) for c in cams),
            key=lambda t: t[0],
        )
        v = cam.centre - np.array([east, north, ground_z])
        dist = float(np.linalg.norm(v))
        bearing = math.degrees(math.atan2(v[0], v[1])) % 360.0
        elevation = math.degrees(math.asin(v[2] / dist))
        log(
            f"  {photo.date} {photo.image[-7:]}  ordering rot{rot} rev{int(rev)} "
            f"homography {h_corr:+.3f} (next {ranked[1][0]:+.3f}), "
            f"rms {cam.rms_px:5.2f} px, orthophoto {corr:+.3f}"
        )
        if corr < min_correlation:
            continue
        if not MIN_ELEVATION_DEG < elevation < MAX_ELEVATION_DEG:
            continue
        kept.append((photo, cam, corr, bearing, elevation, dist))

    log(f"photos with a pose the orthophoto agrees with: {len(kept)}")
    return _spread(kept, max_sources, log)


def _spread(kept, max_sources: int, log) -> list[tuple[Photo, Camera, float]]:
    """Take the best photo of every compass octant, then the second best, and so on.

    A wall faces one way, and only a camera on that side of it can see it, so the
    spread of directions decides coverage far more than the score does. Filling the
    list by score alone piles up on whichever direction the sun and the flight lines
    favoured that year: over Tartu that is north, and eleven north photos of a wall
    that faces south are worth nothing. Round robin over the octants instead, so the
    twenty second photo is the eighth best of its own direction and not the twenty
    second best overall.
    """
    by_octant: dict[int, list] = {}
    for photo, cam, corr, bearing, _elev, _d in sorted(kept, key=lambda t: -t[2]):
        oc = int(((bearing + 22.5) % 360) // 45)
        by_octant.setdefault(oc, []).append((photo, cam, corr, OCTANTS[oc]))
    chosen: list[tuple[Photo, Camera, float, str]] = []
    depth = 0
    while len(chosen) < max_sources:
        row = [v[depth] for v in by_octant.values() if len(v) > depth]
        if not row:
            break
        for item in sorted(row, key=lambda t: -t[2]):
            if len(chosen) >= max_sources:
                break
            chosen.append(item)
        depth += 1
    for photo, _cam, corr, name in chosen:
        log(f"  {name:2s} {photo.date} {photo.image[-7:]} orthophoto {corr:+.3f}")
    counts = {}
    for _p, _c, _corr, name in chosen:
        counts[name] = counts.get(name, 0) + 1
    log("photos per direction: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return [(p, c, corr) for p, c, corr, _ in chosen]


def load(
    cache_path: Path,
    build_fn,
    log=print,
) -> list[tuple[Photo, Camera, float]]:
    """The chosen photos, from the cache file if it holds them, else from ``build_fn``."""
    if cache_path.exists():
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        log(f"photo choice from the cache: {len(raw['sources'])} photos, {cache_path}")
        return [
            (_photo_from_json(s["photo"]), _camera_from_json(s["camera"]), s["correlation"])
            for s in raw["sources"]
        ]
    chosen = build_fn()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "photo": _photo_to_json(p),
                        "camera": _camera_to_json(c),
                        "correlation": corr,
                    }
                    for p, c, corr in chosen
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return chosen


def frames(
    chosen: list[tuple[Photo, Camera, float]], cache_dir: Path, level: int
) -> list[bake.Source]:
    """Fetch every chosen photo at the texture level and wrap it for the baker."""
    out = []
    for photo, cam, _corr in chosen:
        image, offset, _ = fetch_frame(photo, cache_dir, level=level)
        level_w, _ = level_size(photo, level)
        out.append(
            bake.Source(
                photo=photo,
                camera=cam,
                image=np.asarray(image, np.uint8),
                scale=level_w / photo.width,
                offset=offset,
            )
        )
    return out
