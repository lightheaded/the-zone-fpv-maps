"""The laser scan surface, on a point cloud this file writes itself."""

from __future__ import annotations

from pathlib import Path

import laspy
import numpy as np
import pytest

from fpv_maps.crs import BBox
from fpv_maps.lidar import close_gaps, read_surface, smooth
from fpv_maps.terrain import HeightField

BOX = BBox(657000, 6477000, 657020, 6477020)


def write_las(path: Path, x, y, z, classification=2, rgb=None) -> Path:
    """A LAS 1.4 file with colour, the shape the Maa-amet lidar has."""
    header = laspy.LasHeader(version="1.4", point_format=7)
    header.offsets = np.array([BOX.xmin, BOX.ymin, 0.0])
    header.scales = np.array([0.001, 0.001, 0.001])
    las = laspy.LasData(header)
    las.x = np.asarray(x, float)
    las.y = np.asarray(y, float)
    las.z = np.asarray(z, float)
    las.classification = np.full(len(las.x), classification, np.uint8)
    if rgb is not None:
        rgb = np.asarray(rgb, np.uint16)
        las.red, las.green, las.blue = rgb[:, 0] << 8, rgb[:, 1] << 8, rgb[:, 2] << 8
    path.parent.mkdir(parents=True, exist_ok=True)
    las.write(str(path))
    return path


def grid_points(step: float, height):
    """One point per ``step`` metres over the box, at a height from a function."""
    e = np.arange(BOX.xmin + step / 2, BOX.xmax, step)
    n = np.arange(BOX.ymin + step / 2, BOX.ymax, step)
    ee, nn = np.meshgrid(e, n)
    ee, nn = ee.ravel(), nn.ravel()
    return ee, nn, np.asarray(height(ee, nn), float)


def test_the_surface_takes_the_highest_return_in_a_cell(tmp_path):
    """Two points in one cell. The scan surface is the one a drone would hit."""
    x = np.array([657010.2, 657010.6])
    y = np.array([6477010.2, 6477010.6])
    z = np.array([3.0, 11.0])
    path = write_las(tmp_path / "a.las", x, y, z)
    field, _ = read_surface([path], BOX, res_m=1.0)
    assert field.sample_one(657010.5, 6477010.5) == pytest.approx(11.0, abs=1e-3)


def test_a_noise_point_is_not_the_surface(tmp_path):
    """Class 7 is noise. One bird puts a ten metre spike in a roof."""
    real = write_las(tmp_path / "g.las", [657010.5], [6477010.5], [4.0], classification=6)
    bird = write_las(tmp_path / "n.las", [657010.5], [6477010.5], [40.0], classification=7)
    field, _ = read_surface([real, bird], BOX, res_m=1.0)
    assert field.sample_one(657010.5, 6477010.5) == pytest.approx(4.0, abs=1e-3)


def test_only_the_named_classes_are_read(tmp_path):
    ground = write_las(tmp_path / "g.las", [657010.5], [6477010.5], [2.0], classification=2)
    tree = write_las(tmp_path / "t.las", [657010.5], [6477010.5], [18.0], classification=5)
    both, _ = read_surface([ground, tree], BOX, res_m=1.0)
    assert both.sample_one(657010.5, 6477010.5) == pytest.approx(18.0, abs=1e-3)
    bare, _ = read_surface([ground, tree], BOX, res_m=1.0, classes=(2,))
    assert bare.sample_one(657010.5, 6477010.5) == pytest.approx(2.0, abs=1e-3)


def test_the_grid_is_north_up_and_west_left(tmp_path):
    """Row 0 is the north edge, which is the convention the whole pipeline uses."""
    ee, nn, zz = grid_points(0.5, lambda e, n: (n - BOX.ymin) * 0.5)
    path = write_las(tmp_path / "slope.las", ee, nn, zz)
    field, _ = read_surface([path], BOX, res_m=1.0)
    assert field.west == BOX.xmin
    assert field.north == BOX.ymax
    assert field.heights[0, 0] > field.heights[-1, 0], "north must be the high edge"


def test_a_cell_with_no_point_takes_a_measured_height_not_a_median(tmp_path):
    """A hole must not become a pit. The fill is the nearest measurement."""
    ee, nn, zz = grid_points(0.5, lambda e, n: np.full(len(e), 5.0))
    keep = ~((np.abs(ee - 657010.5) < 1.5) & (np.abs(nn - 6477010.5) < 1.5))
    path = write_las(tmp_path / "hole.las", ee[keep], nn[keep], zz[keep])
    field, _ = read_surface([path], BOX, res_m=0.5)
    assert np.isfinite(field.heights).all()
    assert field.sample_one(657010.5, 6477010.5) == pytest.approx(5.0, abs=0.5)


def test_the_colour_comes_from_the_point_that_won_the_cell(tmp_path):
    low = write_las(tmp_path / "low.las", [657010.5], [6477010.5], [1.0], rgb=[[255, 0, 0]])
    high = write_las(tmp_path / "high.las", [657010.5], [6477010.5], [9.0], rgb=[[0, 0, 255]])
    _, image = read_surface([low, high], BOX, res_m=1.0, colour=True)
    assert image is not None
    assert tuple(image[9, 10]) == (0, 0, 255), "the low red point won a cell it lost"


# ------------------------------------------------------------------- the gap closing


def test_the_closing_fills_a_gap_and_keeps_the_edge():
    """The forest case: a canopy with one hole punched to the ground.

    The closing must lift the hole to the canopy and leave the outside boundary of
    the canopy exactly where it was measured.
    """
    a = np.zeros((21, 21))
    a[5:16, 5:16] = 12.0
    a[10, 10] = 0.0
    out = close_gaps(a, radius=2)
    assert out[10, 10] == pytest.approx(12.0), "the gap is still a hole in the canopy"
    assert out[5, 5] == pytest.approx(12.0), "the canopy corner moved"
    assert out[4, 4] == pytest.approx(0.0), "the canopy grew outward"


def test_the_closing_keeps_a_wall_where_it_was_measured():
    a = np.zeros((21, 21))
    a[:, 10:] = 8.0
    out = close_gaps(a, radius=3)
    assert np.allclose(out, a), "a straight edge must survive a closing untouched"


def test_a_radius_of_zero_changes_nothing():
    a = np.arange(25.0).reshape(5, 5)
    assert np.array_equal(close_gaps(a, 0), a)
    assert np.array_equal(smooth(a, 0), a)


def test_the_smoothing_keeps_the_mean():
    rng = np.random.default_rng(1)
    a = rng.normal(10.0, 2.0, (32, 32))
    assert smooth(a, 1).mean() == pytest.approx(a.mean(), abs=1e-9)


# ------------------------------------------------------ a cloud from somewhere else


def test_a_cloud_in_another_projection_lands_in_the_right_place(tmp_path):
    """A survey in UTM 35N must arrive in L-EST97, or the map is 400 km away."""
    from pyproj import Transformer

    to_utm = Transformer.from_crs("EPSG:3301", "EPSG:32635", always_xy=True)
    east, north = 657010.5, 6477010.5
    ux, uy = to_utm.transform(east, north)
    path = write_las(tmp_path / "utm.las", [ux], [uy], [7.0])
    field, _ = read_surface([path], BOX, res_m=1.0, crs="EPSG:32635")
    assert field.sample_one(east, north) == pytest.approx(7.0, abs=1e-3)


def test_a_height_shift_moves_every_point(tmp_path):
    path = write_las(tmp_path / "a.las", [657010.5], [6477010.5], [3.0])
    field, _ = read_surface([path], BOX, res_m=1.0, height_shift_m=-19.0)
    assert field.sample_one(657010.5, 6477010.5) == pytest.approx(-16.0, abs=1e-3)


def test_the_height_shift_is_measured_from_the_ground_points(tmp_path):
    """An ellipsoidal survey sits about 19 m above EH2000. Measure, do not guess.

    Only the ground class may enter the measurement. The trees and the roofs in this
    cloud stand well above the ground and would drag a mean upward.
    """
    from fpv_maps.lidar import measure_height_shift

    ee, nn, _ = grid_points(1.0, lambda e, n: np.zeros(len(e)))
    truth = 12.0
    ground = write_las(tmp_path / "g.las", ee, nn, np.full(len(ee), truth + 19.0))
    canopy = write_las(
        tmp_path / "c.las", ee, nn, np.full(len(ee), truth + 19.0 + 15.0), classification=5
    )
    dtm = HeightField(heights=np.full((20, 20), truth), west=BOX.xmin, north=BOX.ymax, res=1.0)
    shift = measure_height_shift([ground, canopy], dtm)
    assert shift == pytest.approx(-19.0, abs=0.05)


def test_a_cloud_with_no_ground_class_measures_no_shift(tmp_path):
    """Nothing to measure against. Zero is honest and a guess would not be."""
    from fpv_maps.lidar import measure_height_shift

    canopy = write_las(tmp_path / "c.las", [657010.5], [6477010.5], [30.0], classification=5)
    dtm = HeightField(heights=np.zeros((20, 20)), west=BOX.xmin, north=BOX.ymax, res=1.0)
    assert measure_height_shift([canopy], dtm) == 0.0
