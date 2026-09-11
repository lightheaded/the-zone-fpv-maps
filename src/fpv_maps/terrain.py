"""Terrain mesh from a digital terrain model."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh

from fpv_maps.crs import BBox, to_game


@dataclass
class HeightField:
    """A regular grid of heights. Row 0 is north, column 0 is west, 1 cell = ``res`` m."""

    heights: np.ndarray
    west: float
    north: float
    res: float

    def sample(self, east: np.ndarray, north: np.ndarray) -> np.ndarray:
        """Bilinear height at (east, north) points. Points outside clamp to the edge."""
        col = (np.asarray(east, dtype=np.float64) - self.west) / self.res - 0.5
        row = (self.north - np.asarray(north, dtype=np.float64)) / self.res - 0.5
        rows, cols = self.heights.shape
        col = np.clip(col, 0, cols - 1)
        row = np.clip(row, 0, rows - 1)
        c0 = np.floor(col).astype(int)
        r0 = np.floor(row).astype(int)
        c1 = np.minimum(c0 + 1, cols - 1)
        r1 = np.minimum(r0 + 1, rows - 1)
        fc = col - c0
        fr = row - r0
        h = self.heights
        top = h[r0, c0] * (1 - fc) + h[r0, c1] * fc
        bottom = h[r1, c0] * (1 - fc) + h[r1, c1] * fc
        return top * (1 - fr) + bottom * fr

    def sample_one(self, east: float, north: float) -> float:
        return float(self.sample(np.array([east]), np.array([north]))[0])


def fill_nodata(heights: np.ndarray, nodata: float | None) -> np.ndarray:
    """Replace nodata cells with the median of the valid cells."""
    out = np.array(heights, dtype=np.float64)
    mask = ~np.isfinite(out)
    if nodata is not None:
        mask |= out == nodata
    if mask.any():
        valid = out[~mask]
        out[mask] = float(np.median(valid)) if valid.size else 0.0
    return out


def build_terrain(
    field: HeightField,
    bbox: BBox,
    origin: tuple[float, float, float],
    step: float,
) -> trimesh.Trimesh:
    """Grid mesh over ``bbox`` with vertex spacing ``step``, UVs stretched over the box.

    UV (0, 0) is the south west corner and (1, 1) the north east corner. The exporter
    flips V, so row 0 of the ground texture is north, as in the orthophoto.
    """
    nx = int(round(bbox.width / step)) + 1
    ny = int(round(bbox.height / step)) + 1
    east = np.linspace(bbox.xmin, bbox.xmax, nx)
    north = np.linspace(bbox.ymax, bbox.ymin, ny)
    ee, nn = np.meshgrid(east, north)
    hh = field.sample(ee.ravel(), nn.ravel())

    enh = np.column_stack([ee.ravel(), nn.ravel(), hh])
    vertices = to_game(enh, origin)

    uv = np.column_stack(
        [(ee.ravel() - bbox.xmin) / bbox.width, (nn.ravel() - bbox.ymin) / bbox.height]
    )

    idx = np.arange(nx * ny).reshape(ny, nx)
    a = idx[:-1, :-1].ravel()
    b = idx[:-1, 1:].ravel()
    c = idx[1:, :-1].ravel()
    d = idx[1:, 1:].ravel()
    # Counterclockwise seen from above (+Y): north-west, south-west, north-east.
    faces = np.concatenate([np.column_stack([a, c, b]), np.column_stack([b, c, d])])

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.visual = trimesh.visual.TextureVisuals(uv=uv)
    return mesh
