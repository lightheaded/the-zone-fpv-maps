"""Terrain mesh from a digital terrain model.

A small map is one mesh. A large map is a grid of chunks. The game engine draws a
mesh only when the camera can see it, so a chunked terrain costs less on a city map.
Chunks share the lattice of the whole map, so two neighbors have equal edge vertices
and there is no crack between them.
"""

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


@dataclass(frozen=True)
class TerrainGrid:
    """A lattice of terrain points in game axes, row 0 north and column 0 west.

    ``vertices`` is (rows, columns, 3) in meters, (x east, y up, z south).
    ``uv`` is (rows, columns, 2) over the whole map, (0, 0) north west, (1, 1) south east.
    """

    vertices: np.ndarray
    uv: np.ndarray

    @property
    def rows(self) -> int:
        return int(self.vertices.shape[0])

    @property
    def columns(self) -> int:
        return int(self.vertices.shape[1])


def terrain_grid(
    field: HeightField,
    bbox: BBox,
    origin: tuple[float, float, float],
    step: float,
) -> TerrainGrid:
    """Sample ``field`` on a lattice over ``bbox`` with a spacing of about ``step`` meters.

    The lattice always ends on the box edges, so the true spacing is the box side
    divided by a whole number of cells.
    """
    nx = int(round(bbox.width / step)) + 1
    ny = int(round(bbox.height / step)) + 1
    east = np.linspace(bbox.xmin, bbox.xmax, nx)
    north = np.linspace(bbox.ymax, bbox.ymin, ny)
    ee, nn = np.meshgrid(east, north)
    hh = field.sample(ee.ravel(), nn.ravel())

    enh = np.column_stack([ee.ravel(), nn.ravel(), hh])
    vertices = to_game(enh, origin).reshape(ny, nx, 3)
    # V grows south, because glTF reads V = 0 from row 0 of the image and row 0 of
    # the orthophoto is north. A V that grows north turns the ground texture upside
    # down over the whole map: every building then sits on a picture of somewhere
    # else, mirrored about the middle latitude of the box.
    uv = np.stack(
        [(ee - bbox.xmin) / bbox.width, (bbox.ymax - nn) / bbox.height],
        axis=-1,
    )
    return TerrainGrid(vertices=vertices, uv=uv)


def grid_mesh(grid: TerrainGrid, rows: slice, columns: slice) -> trimesh.Trimesh:
    """One mesh from a rectangular part of ``grid``. Two triangles per lattice cell."""
    vertices = grid.vertices[rows, columns].reshape(-1, 3)
    uv = grid.uv[rows, columns].reshape(-1, 2)
    ny, nx = grid.vertices[rows, columns].shape[:2]

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


def build_terrain(
    field: HeightField,
    bbox: BBox,
    origin: tuple[float, float, float],
    step: float,
) -> trimesh.Trimesh:
    """One grid mesh over ``bbox`` with vertex spacing ``step``, UVs stretched over the box.

    UV (0, 0) is the north west corner and (1, 1) the south east corner, which puts
    row 0 of the ground texture at the north edge of the map, as in the orthophoto.
    """
    grid = terrain_grid(field, bbox, origin, step)
    return grid_mesh(grid, slice(None), slice(None))


def split_cells(cells: int, parts: int) -> list[slice]:
    """Split ``cells`` lattice cells into at most ``parts`` runs of points.

    Each slice selects the points of one run. Two neighbors share one point index,
    so the meshes meet without a gap.
    """
    parts = max(1, min(parts, cells))
    edges = [round(i * cells / parts) for i in range(parts + 1)]
    return [slice(edges[i], edges[i + 1] + 1) for i in range(parts)]


def build_terrain_chunks(
    field: HeightField,
    bbox: BBox,
    origin: tuple[float, float, float],
    step: float,
    chunk_m: float,
) -> dict[str, trimesh.Trimesh]:
    """Grid meshes over ``bbox``, each about ``chunk_m`` meters wide.

    A ``chunk_m`` of 0 or less gives one mesh named ``terrain``. Otherwise the names
    are ``terrain_r<row>c<column>``, row 0 north and column 0 west.
    """
    grid = terrain_grid(field, bbox, origin, step)
    if chunk_m <= 0:
        return {"terrain": grid_mesh(grid, slice(None), slice(None))}
    row_runs = split_cells(grid.rows - 1, max(1, round(bbox.height / chunk_m)))
    column_runs = split_cells(grid.columns - 1, max(1, round(bbox.width / chunk_m)))
    out: dict[str, trimesh.Trimesh] = {}
    for r, rows in enumerate(row_runs):
        for c, columns in enumerate(column_runs):
            out[f"terrain_r{r:02d}c{c:02d}"] = grid_mesh(grid, rows, columns)
    return out
