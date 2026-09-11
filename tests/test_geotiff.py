"""Reading Maa-amet GeoTIFF sheets. The test writes its own sheet, so no network is used."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from fpv_maps.crs import BBox
from fpv_maps.geotiff import dtm_resolution, read_heights

NODATA = -9999.0


def write_sheet(path: Path, heights: np.ndarray, west: float, north: float, res: float) -> Path:
    profile = {
        "driver": "GTiff",
        "height": heights.shape[0],
        "width": heights.shape[1],
        "count": 1,
        "dtype": "float32",
        "nodata": NODATA,
        "crs": "EPSG:3301",
        "transform": from_origin(west, north, res, res),
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(heights.astype("float32"), 1)
    return path


def test_dtm_resolution_is_two_cells_per_step():
    assert dtm_resolution(2.0, native_m=1.0) == 1.0
    assert dtm_resolution(10.0, native_m=1.0) == 5.0
    assert dtm_resolution(0.5, native_m=1.0) == 1.0


def test_read_heights_needs_a_sheet():
    with pytest.raises(ValueError, match="no DTM"):
        read_heights([], BBox(0, 0, 10, 10))


def test_read_heights_keeps_the_native_resolution(tmp_path: Path):
    heights = np.arange(100 * 100, dtype="float32").reshape(100, 100)
    sheet = write_sheet(tmp_path / "a.tif", heights, west=0.0, north=100.0, res=1.0)
    field = read_heights([sheet], BBox(10, 10, 90, 90), pad_m=4.0)
    assert field.res == 1.0
    assert field.heights.shape == (88, 88)


def test_read_heights_averages_when_it_decimates(tmp_path: Path):
    heights = np.full((100, 100), 40.0, dtype="float32")
    heights[:50, :50] = 60.0
    sheet = write_sheet(tmp_path / "a.tif", heights, west=0.0, north=100.0, res=1.0)
    field = read_heights([sheet], BBox(0, 0, 100, 100), pad_m=0.0, res_m=5.0)
    assert field.res == 5.0
    assert field.heights.shape == (20, 20)
    assert field.heights[0, 0] == 60.0
    assert field.heights[-1, -1] == 40.0


def test_read_heights_does_not_average_nodata_into_the_terrain(tmp_path: Path):
    """GDAL leaves nodata cells out of the average, so no pit appears at a data hole."""
    heights = np.full((100, 100), 40.0, dtype="float32")
    heights[0, 0] = NODATA
    sheet = write_sheet(tmp_path / "a.tif", heights, west=0.0, north=100.0, res=1.0)
    field = read_heights([sheet], BBox(0, 0, 100, 100), pad_m=0.0, res_m=5.0)
    assert field.heights.min() == 40.0 and field.heights.max() == 40.0
