"""Score a resected camera against the orthophoto.

The four published corners lie on the ground, and four coplanar points barely pin down
a camera: a wrong pose can still fit them to a few pixels. So the corner residual is
not a test of the pose. The orthophoto is. Project open ground into the photo, sample
it, and correlate with the orthophoto at the same points. A right pose correlates; a
wrong one does not.

Measured over Tartu old town, a right pose scores 0.33 to 0.60 and a wrong one scores
about zero, so one threshold separates them with a wide margin.
"""

from __future__ import annotations

import math

import numpy as np
from shapely import contains_xy
from shapely.geometry import MultiPoint

from fpv_maps.buildings import BuildingSet
from fpv_maps.crs import BBox
from fpv_maps.terrain import HeightField


def ground_control(
    bbox: BBox,
    ortho_rgb: np.ndarray,
    buildings: BuildingSet,
    field: HeightField,
    n: int = 180,
    buffer_m: float = 12.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Open ground points as (east, north, height), and their orthophoto luminance.

    ``ortho_rgb`` is the ground texture of the map, which covers ``bbox`` exactly.
    Points near a building are dropped. A wall leans in an oblique photo, so a ground
    pixel beside it is not the pixel the orthophoto shows there, and it would score a
    right pose down.
    """
    lum = ortho_rgb.astype(np.float32).mean(axis=2)
    rows, cols = lum.shape
    ee, nn = np.meshgrid(
        np.linspace(bbox.xmin + 5, bbox.xmax - 5, n),
        np.linspace(bbox.ymax - 5, bbox.ymin + 5, n),
    )
    pts = np.column_stack([ee.ravel(), nn.ravel()])
    keep = np.ones(len(pts), bool)
    for building in buildings.buildings:
        v = building.vertices[:, :2]
        lo = v.min(axis=0) - buffer_m
        hi = v.max(axis=0) + buffer_m
        near = ((pts >= lo) & (pts <= hi)).all(axis=1)
        if not near.any():
            continue
        idx = np.flatnonzero(near)
        footprint = MultiPoint(v).convex_hull.buffer(buffer_m)
        keep[idx] &= ~contains_xy(footprint, pts[near, 0], pts[near, 1])
    pts = pts[keep]
    col = np.clip(((pts[:, 0] - bbox.xmin) / bbox.width * cols).astype(int), 0, cols - 1)
    row = np.clip(((bbox.ymax - pts[:, 1]) / bbox.height * rows).astype(int), 0, rows - 1)
    z = field.sample(pts[:, 0], pts[:, 1])
    return np.column_stack([pts[:, 0], pts[:, 1], z]), lum[row, col]


def _correlate(
    image: np.ndarray, x: np.ndarray, y: np.ndarray, ok: np.ndarray, lum: np.ndarray
) -> tuple[float, int]:
    """Normalised correlation of the photo and the orthophoto at the kept points."""
    if ok.sum() < 400:
        return 0.0, int(ok.sum())
    gray = image if image.ndim == 2 else image.mean(axis=2)
    a = gray[y[ok].astype(int), x[ok].astype(int)].astype(float)
    b = lum[ok].astype(float)
    a = a - a.mean()
    b = b - b.mean()
    den = math.sqrt(float((a * a).sum()) * float((b * b).sum()))
    return (float((a * b).sum()) / den if den > 0 else 0.0), int(ok.sum())


def score(camera, image, scale, offset, gc_pts, gc_lum) -> tuple[float, int]:
    """How well the camera agrees with the orthophoto. 1.0 is perfect, 0.0 is nothing."""
    uv, depth = camera.project(gc_pts)
    x = (uv[:, 0] + camera.width / 2.0) * scale - offset[0]
    y = (uv[:, 1] + camera.height / 2.0) * scale - offset[1]
    h, w = image.shape[:2]
    ok = (depth > 0) & (x >= 0) & (x < w - 1) & (y >= 0) & (y < h - 1)
    return _correlate(image, x, y, ok, gc_lum)


def homography(src, dst) -> np.ndarray:
    """The 3x3 that maps the ``src`` points to the ``dst`` points, from four pairs."""
    a = []
    for (x, y), (u, v) in zip(src, dst, strict=True):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, vt = np.linalg.svd(np.array(a, float))
    return vt[-1].reshape(3, 3)


def best_ordering(photo, image, scale, offset, gc_pts, gc_lum) -> list[tuple[float, int, bool]]:
    """Which frame corner is which published corner, decided by the orthophoto.

    The API gives the four ground corners as a ring with no clue which one is the top
    left of the frame. All eight readings of the ring fit the corners equally well, and
    they are different cameras, so the residual cannot choose. A plane homography needs
    no camera at all: map open ground into the photo through each reading, and keep the
    one that agrees with the orthophoto. On Tartu the winner leads by a factor of five.

    Returns ``(correlation, rotation, reversed)`` for all eight, best first.
    """
    w, h = photo.width, photo.height
    frame = [(-w / 2, -h / 2), (-w / 2, h / 2), (w / 2, h / 2), (w / 2, -h / 2)]
    corners = np.array(photo.corners, float)
    ground = np.column_stack([gc_pts[:, 0], gc_pts[:, 1], np.ones(len(gc_pts))])
    gray = image if image.ndim == 2 else image.mean(axis=2)
    ih, iw = gray.shape
    out = []
    for rot in range(4):
        for rev in (False, True):
            idx = list(range(4))[rot:] + list(range(4))[:rot]
            if rev:
                idx = idx[::-1]
            mat = homography([corners[i] for i in idx], frame)
            q = ground @ mat.T
            with np.errstate(divide="ignore", invalid="ignore"):
                x = (q[:, 0] / q[:, 2] + w / 2) * scale - offset[0]
                y = (q[:, 1] / q[:, 2] + h / 2) * scale - offset[1]
            ok = np.isfinite(x) & np.isfinite(y) & (q[:, 2] != 0)
            ok &= (x >= 0) & (x < iw - 1) & (y >= 0) & (y < ih - 1)
            corr, _ = _correlate(gray, x, y, ok, gc_lum)
            out.append((corr, rot, rev))
    out.sort(key=lambda t: -t[0])
    return out
