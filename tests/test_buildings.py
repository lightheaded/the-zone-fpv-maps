from pathlib import Path

import numpy as np

from fpv_maps.buildings import (
    build_building_chunks,
    build_building_meshes,
    chunk_buildings,
    read_obj,
    read_offset,
)
from fpv_maps.crs import BBox

OBJ = """# two boxes, FME style: one usemtl block per building, no groups
mtllib x.mtl
v 0 0 0
v 10 0 0
v 10 10 0
v 0 10 0
v 0 0 5
v 10 0 5
v 10 10 5
v 0 10 5
usemtl building_a
f 1 4 3 2
f 5 6 7 8
f 1 2 6 5
f 2 3 7 6
f 3 4 8 7
f 4 1 5 8
v 100 100 0
v 101 100 0
v 101 101 0
v 100 101 0
v 100.5 100.5 3
usemtl building_b
f 9 10 11 12
f 9 10 13
f 10 11 13
f 11 12 13
f 12 9 13
"""


def test_read_offset(tmp_path: Path):
    fwt = tmp_path / "x.fwt"
    fwt.write_text("1 0 0 654513.2879999988\n0 1 0 6475676.235000001\n0 0 1 62.6452999999965\n")
    assert read_offset(fwt) == (654513.2879999988, 6475676.235000001, 62.6452999999965)
    fwt.write_text("654513.288 6475676.235 62.645\n")
    assert read_offset(fwt) == (654513.288, 6475676.235, 62.645)


def test_read_obj_splits_per_usemtl(tmp_path: Path):
    obj = tmp_path / "x.obj"
    obj.write_text(OBJ)
    bs = read_obj(obj, offset=(1000.0, 2000.0, 50.0))
    assert len(bs) == 2
    a, b = bs.buildings
    assert a.name == "building_a" and len(a.faces) == 12 and len(a.vertices) == 8
    assert b.name == "building_b" and len(b.faces) == 6 and len(b.vertices) == 5
    assert a.centroid == (1005.0, 2005.0)
    assert np.isclose(a.vertices[:, 2].max(), 55.0)


def test_inside_and_meshes(tmp_path: Path):
    obj = tmp_path / "x.obj"
    obj.write_text(OBJ)
    bs = read_obj(obj)
    inside = bs.inside(BBox(-1, -1, 50, 50))
    assert [b.name for b in inside.buildings] == ["building_a"]
    meshes = build_building_meshes(inside, (0.0, 0.0, 0.0), "z_concrete2", "z_pebbled_asphalt")
    # 2 roof triangles (top face), 10 others are walls and the floor.
    assert len(meshes["roofs"].faces) == 2
    assert len(meshes["walls"].faces) == 10
    assert meshes["roofs"].visual.material.name == "z_pebbled_asphalt"
    assert meshes["walls"].visual.material.name == "z_concrete2"
    # Roof at height 5 in game y.
    assert np.allclose(meshes["roofs"].vertices[:, 1], 5.0)


def test_chunk_buildings_by_centroid(tmp_path: Path):
    obj = tmp_path / "x.obj"
    obj.write_text(OBJ)
    bs = read_obj(obj)
    # A 200 m box with 100 m chunks: building_a is at (5, 5), building_b at (100.4, 100.4).
    box = BBox(0, 0, 200, 200)
    chunks = chunk_buildings(bs, box, chunk_m=100.0)
    # Row 0 is north, so the building in the south west corner is row 1, column 0.
    assert sorted(chunks) == ["r00c01", "r01c00"]
    assert [b.name for b in chunks["r01c00"].buildings] == ["building_a"]
    assert [b.name for b in chunks["r00c01"].buildings] == ["building_b"]
    assert list(chunk_buildings(bs, box, chunk_m=0.0)) == [""]


def test_build_building_chunks_names_and_shared_materials(tmp_path: Path):
    obj = tmp_path / "x.obj"
    obj.write_text(OBJ)
    bs = read_obj(obj)
    box = BBox(0, 0, 200, 200)
    meshes = build_building_chunks(bs, box, (0.0, 0.0, 0.0), "z_w", "z_r", chunk_m=100.0)
    assert set(meshes) == {
        "buildings_r01c00_walls",
        "buildings_r01c00_roofs",
        "buildings_r00c01_walls",
        "buildings_r00c01_roofs",
    }
    # Every chunk points at the same two material objects, so the file holds two.
    walls = {id(m.visual.material) for k, m in meshes.items() if k.endswith("_walls")}
    assert len(walls) == 1
    assert meshes["buildings_r01c00_walls"].visual.material.name == "z_w"

    plain = build_building_chunks(bs, box, (0.0, 0.0, 0.0), "z_w", "z_r", chunk_m=0.0)
    assert set(plain) == {"buildings_walls", "buildings_roofs"}


def test_triangle_count(tmp_path: Path):
    obj = tmp_path / "x.obj"
    obj.write_text(OBJ)
    assert read_obj(obj).triangles() == 18
