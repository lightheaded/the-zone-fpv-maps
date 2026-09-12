from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from fpv_maps.crs import BBox
from fpv_maps.drone import (
    DroneSources,
    block_transform,
    measure_vertical_shift,
    read_drone_heights,
    read_drone_rgb,
    select_tiles,
    tile_levels,
)

BOX = BBox(657800, 6477900, 657900, 6478000)


def write_raster(path: Path, values: np.ndarray, crs: str = "EPSG:3301", res: float = 1.0) -> Path:
    """A single band GeoTIFF over ``BOX``, row 0 at the north edge."""
    height, width = values.shape
    transform = from_origin(BOX.xmin, BOX.ymax, res, res)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=np.nan,
    ) as dst:
        dst.write(values.astype("float32"), 1)
    return path


def write_rgb(path: Path, values: np.ndarray, res: float = 1.0) -> Path:
    height, width = values.shape[:2]
    transform = from_origin(BOX.xmin, BOX.ymax, res, res)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=3,
        dtype="uint8",
        crs="EPSG:3301",
        transform=transform,
    ) as dst:
        for band in range(3):
            dst.write(values[:, :, band], band + 1)
    return path


# ------------------------------------------------------------------ sources


def test_drone_sources_is_false_when_empty():
    assert not DroneSources()
    assert DroneSources(elevation=(Path("a.tif"),))


# ------------------------------------------------------------------ rasters


def test_read_drone_heights_returns_the_values(tmp_path):
    path = write_raster(tmp_path / "dsm.tif", np.full((100, 100), 42.0))
    field = read_drone_heights((path,), BOX, res_m=2.0)
    assert math.isclose(field.sample_one(657850, 6477950), 42.0, abs_tol=1e-3)


def test_read_drone_heights_needs_a_source():
    with pytest.raises(ValueError, match="no drone elevation"):
        read_drone_heights((), BOX, res_m=1.0)


def test_read_drone_rgb_keeps_the_base_outside_the_survey(tmp_path):
    # A survey raster that only covers the north half of the box, and a base over all
    # of it. Coverage is the footprint of the file, not the color of its pixels.
    survey = np.full((50, 100, 3), 90, dtype="uint8")
    survey[:, :, 0] = 10
    path = write_rgb(tmp_path / "ortho.tif", survey)
    base = np.full((64, 64, 3), 200, dtype="uint8")
    out = read_drone_rgb((path,), BOX, 64, base=base)
    assert out.shape == (64, 64, 3)
    # Row 0 is the north edge, which the survey covers.
    assert tuple(out[5, 32]) == (10, 90, 90)
    # The south half has no survey, so the base shows through instead of black.
    assert tuple(out[60, 32]) == (200, 200, 200)


def test_read_drone_rgb_keeps_black_pixels_of_the_survey(tmp_path):
    """A black pixel inside the survey is a real color, not a hole."""
    path = write_rgb(tmp_path / "ortho.tif", np.zeros((100, 100, 3), dtype="uint8"))
    base = np.full((64, 64, 3), 200, dtype="uint8")
    out = read_drone_rgb((path,), BOX, 64, base=base)
    assert out.max() == 0


def test_read_drone_rgb_without_a_base_fills_the_rest_with_black(tmp_path):
    survey = np.full((50, 100, 3), 90, dtype="uint8")
    path = write_rgb(tmp_path / "ortho.tif", survey)
    out = read_drone_rgb((path,), BOX, 64)
    assert tuple(out[5, 32]) == (90, 90, 90)
    assert tuple(out[60, 32]) == (0, 0, 0)


def test_read_drone_rgb_rejects_a_base_of_another_size(tmp_path):
    path = write_rgb(tmp_path / "ortho.tif", np.zeros((10, 10, 3), dtype="uint8"))
    with pytest.raises(ValueError, match="base orthophoto is"):
        read_drone_rgb((path,), BOX, 64, base=np.zeros((32, 32, 3), dtype="uint8"))


# ------------------------------------------------------- the vertical shift


def test_measure_vertical_shift_finds_a_flat_offset(tmp_path):
    open_data = write_raster(tmp_path / "dtm.tif", np.full((100, 100), 40.0))
    survey = write_raster(tmp_path / "survey.tif", np.full((100, 100), 59.0))
    # The survey stands 19 m above the open model, so 19 m must come off it.
    assert math.isclose(measure_vertical_shift((survey,), [open_data], BOX), -19.0, abs_tol=0.1)


def test_measure_vertical_shift_ignores_buildings_and_trees(tmp_path):
    """A surface model is never below the ground, so the peak, not the median, is right."""
    open_data = write_raster(tmp_path / "dtm.tif", np.full((200, 200), 40.0), res=0.5)
    surface = np.full((200, 200), 59.0)
    # Fill 65 percent of the box with roofs and trees, 3 to 12 m above the ground.
    # Over half, so that the median of the difference is wrong and the peak is right.
    rng = np.random.default_rng(0)
    tall = rng.random((200, 200)) < 0.65
    surface[tall] += rng.uniform(3.0, 12.0, size=int(tall.sum()))
    survey = write_raster(tmp_path / "surface.tif", surface, res=0.5)
    shift = measure_vertical_shift((survey,), [open_data], BOX)
    assert math.isclose(shift, -19.0, abs_tol=0.2)
    # The median would be pulled well away by the same data.
    assert abs(np.median(40.0 - surface) + 19.0) > 1.0


def test_measure_vertical_shift_needs_an_overlap(tmp_path):
    open_data = write_raster(tmp_path / "dtm.tif", np.full((100, 100), 40.0))
    empty = write_raster(tmp_path / "empty.tif", np.full((100, 100), np.nan))
    with pytest.raises(ValueError, match="do not overlap"):
        measure_vertical_shift((empty,), [open_data], BOX)


# ---------------------------------------------------------------- 3D Tiles


def make_tileset(root: Path) -> Path:
    """A two level pyramid in one block, in the shape that DJI Terra writes.

    The root holds a coarse tile and links to one JSON child per finer node. Each of
    those files holds its own tile and its own children.
    """
    block = root / "BlockA"
    block.mkdir(parents=True)
    identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    (block / "tileset.json").write_text(
        json.dumps(
            {
                "asset": {"gltfUpAxis": "Z", "version": "0.0"},
                "geometricError": 4.0,
                "root": {
                    "transform": identity,
                    "geometricError": 2.0,
                    "content": {"uri": "BlockA_L15_1.b3dm"},
                    "children": [
                        {"content": {"uri": "BlockA_L16_1.json"}, "geometricError": 1e10},
                        {"content": {"uri": "BlockA_L16_2.json"}, "geometricError": 1e10},
                    ],
                },
            }
        )
    )
    for index in (1, 2):
        (block / f"BlockA_L16_{index}.json").write_text(
            json.dumps(
                {
                    "asset": {"gltfUpAxis": "Z", "version": "0.0"},
                    "geometricError": 1.0,
                    "root": {
                        "geometricError": 0.5,
                        "content": {"uri": f"BlockA_L16_{index}.b3dm"},
                        "children": [
                            {
                                "content": {"uri": f"BlockA_L17_{index}.json"},
                                "geometricError": 1e10,
                            }
                        ],
                    },
                }
            )
        )
        (block / f"BlockA_L17_{index}.json").write_text(
            json.dumps(
                {
                    "asset": {"gltfUpAxis": "Z", "version": "0.0"},
                    "geometricError": 0.25,
                    "root": {
                        "geometricError": 0.1,
                        "content": {"uri": f"BlockA_L17_{index}.b3dm"},
                    },
                }
            )
        )
    for name in ("BlockA_L15_1", "BlockA_L16_1", "BlockA_L16_2", "BlockA_L17_1", "BlockA_L17_2"):
        (block / f"{name}.b3dm").write_bytes(b"b3dm")
    return root


def test_select_tiles_stops_at_the_asked_quality(tmp_path):
    root = make_tileset(tmp_path / "terra_b3dms")
    # The root alone is good enough for 2 m of error.
    assert [p.name for p, _ in select_tiles(root, 2.0)] == ["BlockA_L15_1.b3dm"]
    # 0.5 m needs the two middle tiles, and no deeper.
    assert [p.name for p, _ in select_tiles(root, 0.5)] == [
        "BlockA_L16_1.b3dm",
        "BlockA_L16_2.b3dm",
    ]
    # 0.1 m reaches the leaves.
    assert [p.name for p, _ in select_tiles(root, 0.1)] == [
        "BlockA_L17_1.b3dm",
        "BlockA_L17_2.b3dm",
    ]


def test_select_tiles_covers_the_site_once(tmp_path):
    """Every selection must be a cut across the tree, never a tile and its child."""
    root = make_tileset(tmp_path / "terra_b3dms")
    for error in (4.0, 2.0, 1.0, 0.5, 0.25, 0.1, 0.0):
        names = [p.name for p, _ in select_tiles(root, error)]
        assert len(names) == len(set(names))
        levels = {int(n.split("_L")[1].split("_")[0]) for n in names}
        # One level per branch: a mixed cut is allowed, a parent with its child is not.
        assert not ({15} & levels and {16, 17} & levels)


def test_select_tiles_with_no_limit_takes_the_leaves(tmp_path):
    root = make_tileset(tmp_path / "terra_b3dms")
    assert [p.name for p, _ in select_tiles(root, 0.0)] == [
        "BlockA_L17_1.b3dm",
        "BlockA_L17_2.b3dm",
    ]


def test_select_tiles_ignores_a_folder_with_no_tileset(tmp_path):
    root = make_tileset(tmp_path / "terra_b3dms")
    (root / "notes").mkdir()
    assert len(select_tiles(root, 0.5)) == 2


def test_tile_levels_counts_the_pyramid(tmp_path):
    root = make_tileset(tmp_path / "terra_b3dms")
    assert tile_levels(root) == {15: 1, 16: 2, 17: 2}


def test_block_transform_reads_column_first(tmp_path):
    root = make_tileset(tmp_path / "terra_b3dms")
    block = root / "BlockA"
    (block / "tileset.json").write_text(
        json.dumps(
            {
                "asset": {"version": "0.0"},
                "geometricError": 1.0,
                # 3D Tiles stores a matrix column first, so the position is the last four.
                "root": {"transform": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 10, 20, 30, 1]},
            }
        )
    )
    matrix = block_transform(block)
    assert matrix.shape == (4, 4)
    assert list(matrix[:3, 3]) == [10.0, 20.0, 30.0]
