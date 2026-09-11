"""Read Maa-amet GeoTIFF sheets into arrays for one bounding box."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.merge import merge

from fpv_maps.crs import BBox
from fpv_maps.terrain import HeightField, fill_nodata


def dtm_resolution(step_m: float, native_m: float) -> float:
    """The cell size to read the elevation model at for a terrain of spacing ``step_m``.

    Two cells per terrain step keep every hill that the mesh can show. The result is
    never finer than the data. A whole city at 1 m would need too much memory: 81 km
    square is 81 million cells.
    """
    return max(native_m, step_m / 2.0)


def read_heights(
    paths: list[Path], bbox: BBox, pad_m: float = 4.0, res_m: float | None = None
) -> HeightField:
    """Merge DTM sheets and return the heights over ``bbox`` plus a margin.

    ``res_m`` is the cell size in meters. The default is the cell size of the data.
    A larger value averages the cells while they are read and saves memory.
    """
    if not paths:
        raise ValueError("no DTM sheets given")
    box = bbox.buffer(pad_m)
    sources = [rasterio.open(p) for p in paths]
    try:
        res = float(res_m or sources[0].res[0])
        nodata = sources[0].nodata
        data, transform = merge(
            sources,
            bounds=box.as_tuple(),
            res=(res, res),
            nodata=nodata,
            resampling=Resampling.average,
        )
    finally:
        for src in sources:
            src.close()
    heights = fill_nodata(data[0], nodata)
    return HeightField(heights=heights, west=transform.c, north=transform.f, res=transform.a)


def read_rgb(paths: list[Path], bbox: BBox, size_px: int) -> np.ndarray:
    """Merge orthophoto sheets and resample the box to ``size_px`` square, uint8 RGB."""
    if not paths:
        raise ValueError("no orthophoto sheets given")
    res = (bbox.width / size_px, bbox.height / size_px)
    sources = [rasterio.open(p) for p in paths]
    try:
        data, _ = merge(
            sources,
            bounds=bbox.as_tuple(),
            res=res,
            indexes=[1, 2, 3],
            resampling=Resampling.average,
        )
    finally:
        for src in sources:
            src.close()
    rgb = np.moveaxis(data, 0, -1)
    if rgb.dtype != np.uint8:
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    return rgb
