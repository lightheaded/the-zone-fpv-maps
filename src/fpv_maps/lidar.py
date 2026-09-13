"""A map surface measured by an aerial laser scanner.

Every other map in this repository builds its world from two derived products: a
digital terrain model for the ground and the LOD2 vector model for the houses. Both
are interpretations. The terrain model has the buildings and the trees removed from
it, and an LOD2 building is a box with a roof shape fitted to it, so a map made of the
two holds no tree, no fence, no mast, no greenhouse and no house that is not a box.

The Maa- ja Ruumiamet lidar is the measurement those products are derived from. Over
Tartu the 2024 flight has 23 to 29 points per square metre, and every point carries a
colour and a near infrared value as well as a height and a classification. That is
enough to build the surface directly.

The result is a 2.5D surface: one height per cell, taken from the highest return. It
holds the trees, the roofs, the walls as steep steps, the poles and the wires, and it
cannot hold an overhang or the underside of anything. For a drone flying over a
village that is the right trade. For flying through an archway it is not.

Class codes follow the ASPRS standard, which Maa-amet uses:
2 ground, 3 to 5 vegetation low to high, 6 building, 9 water, 7 noise.
"""

from __future__ import annotations

import math
from pathlib import Path

import laspy
import numpy as np

from fpv_maps.crs import BBox
from fpv_maps.terrain import HeightField

#: Points the scanner never should have kept. 7 is noise and 18 is a high point, which
#: over a village is a bird or a reflection off a window. A single one of these lifts a
#: cell by ten metres and puts a spike in the mesh.
NOISE_CLASSES = (7, 18)

#: Read the file in blocks. A 1 km sheet at 29 points per square metre is 29 million
#: points, and every dimension of one is another 29 million values in memory.
CHUNK = 4_000_000


def _grid_index(x: np.ndarray, y: np.ndarray, bbox: BBox, res: float, shape) -> np.ndarray:
    rows, cols = shape
    col = np.floor((x - bbox.xmin) / res).astype(np.int64)
    row = np.floor((bbox.ymax - y) / res).astype(np.int64)
    inside = (col >= 0) & (col < cols) & (row >= 0) & (row < rows)
    idx = np.full(len(x), -1, dtype=np.int64)
    idx[inside] = row[inside] * cols + col[inside]
    return idx


def read_surface(
    paths: list[Path] | tuple[Path, ...],
    bbox: BBox,
    res_m: float,
    classes: tuple[int, ...] | None = None,
    colour: bool = False,
    close_cells: int = 0,
    smooth_cells: int = 0,
) -> tuple[HeightField, np.ndarray | None]:
    """The highest return in every cell of ``bbox``, and optionally its colour.

    ``classes`` keeps only those classification codes. ``None`` keeps everything
    except the noise classes, which is the surface a drone would hit.

    ``close_cells`` is the radius of a morphological closing over the finished grid.
    Over woodland it is the difference between a canopy and a field of spikes. See
    ``close_gaps``.

    Returns the height field and, when ``colour`` is set, an (rows, cols, 3) uint8
    image of the colour of the highest return, in the same grid. A cell with no point
    in it is filled from its neighbours, because a hole in a height field is a hole in
    the world.
    """
    if not paths:
        raise ValueError("no lidar files given")
    cols = max(1, int(round(bbox.width / res_m)))
    rows = max(1, int(round(bbox.height / res_m)))
    shape = (rows, cols)
    top = np.full(rows * cols, -np.inf, dtype=np.float32)
    rgb = np.zeros((rows * cols, 3), dtype=np.uint16) if colour else None

    for path in paths:
        with laspy.open(str(path)) as reader:
            has_colour = colour and "red" in reader.header.point_format.dimension_names
            for points in reader.chunk_iterator(CHUNK):
                x = np.asarray(points.x)
                y = np.asarray(points.y)
                idx = _grid_index(x, y, bbox, res_m, shape)
                keep = idx >= 0
                if not keep.any():
                    continue
                cls = np.asarray(points.classification)[keep]
                wanted = (
                    np.isin(cls, classes) if classes is not None else ~np.isin(cls, NOISE_CLASSES)
                )
                if not wanted.any():
                    continue
                cell = idx[keep][wanted]
                z = np.asarray(points.z)[keep][wanted].astype(np.float32)
                # np.maximum.at is the only way to reduce by key without sorting the
                # whole block, and a 1 km sheet is 29 million points.
                np.maximum.at(top, cell, z)
                if has_colour:
                    # A second pass over the same block writes the colour of the point
                    # that won its cell. Doing it in one pass needs an argmax by key,
                    # which numpy has no primitive for and which costs a sort.
                    won = z >= top[cell]
                    c = cell[won]
                    for band, name in enumerate(("red", "green", "blue")):
                        rgb[c, band] = np.asarray(getattr(points, name))[keep][wanted][won] >> 8

    empty = ~np.isfinite(top)
    heights = np.where(empty, np.nan, top).reshape(shape).astype(np.float64)
    heights = _fill_holes(heights)
    if close_cells:
        heights = close_gaps(heights, close_cells)
    if smooth_cells:
        heights = smooth(heights, smooth_cells)
    field = HeightField(heights=heights, west=bbox.xmin, north=bbox.ymax, res=res_m)
    image = rgb.reshape(rows, cols, 3).astype(np.uint8) if colour else None
    return field, image


def _window(a: np.ndarray, radius: int, op) -> np.ndarray:
    """Separable sliding window of ``op`` over a square of ``2 * radius + 1`` cells."""
    out = a
    for axis in (0, 1):
        acc = out
        for shift in range(1, radius + 1):
            acc = op(acc, np.roll(out, shift, axis=axis))
            acc = op(acc, np.roll(out, -shift, axis=axis))
        out = acc
    return out


def close_gaps(heights: np.ndarray, radius: int) -> np.ndarray:
    """Morphological closing: a maximum window, then a minimum window of the same size.

    A forest is the reason this exists. Between the branches the beam reaches the
    ground, so the highest return in one 30 cm cell is a treetop and in the cell
    beside it the bare earth, fifteen metres lower. Meshed as it stands, that is not a
    canopy. It is a field of vertical curtains, one per gap, and it is the first thing
    a person sees in the map.

    The maximum window closes every gap narrower than the window. The minimum window
    then takes back the growth it caused, so a roof edge and a wall stay where they
    were measured and only the holes stay filled. Anything thinner than the window
    survives as a bump rather than a spike, which is the right answer for a twig and
    the wrong one for a mast. A mast is worth less than a flyable forest.
    """
    if radius < 1:
        return heights
    return _window(_window(heights, radius, np.maximum), radius, np.minimum)


def smooth(heights: np.ndarray, radius: int) -> np.ndarray:
    """Mean over a square window. Takes the last jaggedness out of a closed canopy."""
    if radius < 1:
        return heights
    out = np.zeros_like(heights)
    n = 0
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            out += np.roll(np.roll(heights, dr, axis=0), dc, axis=1)
            n += 1
    return out / n


def _fill_holes(heights: np.ndarray) -> np.ndarray:
    """Give every empty cell the nearest measured height, by widening rings.

    A cell with no return is water, a shadow behind a roof, or a gap between flight
    lines. Leaving it at nothing tears the mesh. Taking the median of the whole sheet,
    which is what the raster path does, drops a pit into a roof. The nearest measured
    height is the only fill that keeps a surface continuous.
    """
    out = np.array(heights, dtype=np.float64)
    hole = ~np.isfinite(out)
    if not hole.any():
        return out
    if hole.all():
        return np.zeros_like(out)
    filled = np.where(hole, 0.0, out)
    weight = (~hole).astype(np.float64)
    # A few box blurs of the valid cells spread the measured heights into the holes.
    # Each pass doubles the reach, so a hole of n cells closes in about log2(n) passes.
    for _ in range(int(math.ceil(math.log2(max(out.shape)))) + 1):
        if weight.min() > 0:
            break
        filled, weight = _spread(filled, weight)
    return np.where(hole, filled / np.maximum(weight, 1e-9), out)


def _spread(values: np.ndarray, weight: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """One pass of a 3 x 3 sum over the values and their weights."""
    v = np.zeros_like(values)
    w = np.zeros_like(weight)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            v += np.roll(np.roll(values, dr, axis=0), dc, axis=1)
            w += np.roll(np.roll(weight, dr, axis=0), dc, axis=1)
    return v, w
