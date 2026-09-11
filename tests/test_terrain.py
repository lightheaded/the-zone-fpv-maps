import numpy as np

from fpv_maps.terrain import (
    HeightField,
    build_terrain,
    build_terrain_chunks,
    fill_nodata,
    split_cells,
)


def test_sample_bilinear():
    heights = np.array([[0.0, 10.0], [20.0, 30.0]])
    field = HeightField(heights=heights, west=0.0, north=2.0, res=1.0)
    # Cell centers: (0.5, 1.5) -> 0, (1.5, 1.5) -> 10, (0.5, 0.5) -> 20.
    assert field.sample_one(0.5, 1.5) == 0.0
    assert field.sample_one(1.5, 1.5) == 10.0
    assert field.sample_one(0.5, 0.5) == 20.0
    assert field.sample_one(1.0, 1.0) == 15.0


def test_fill_nodata_uses_median():
    out = fill_nodata(np.array([[1.0, -9999.0], [3.0, np.nan]]), -9999.0)
    assert out[0, 1] == 2.0 and out[1, 1] == 2.0


def test_build_terrain_grid(bbox, flat_field):
    origin = (662500.0, 6473500.0, 40.0)
    mesh = build_terrain(flat_field, bbox, origin, step=100.0)
    assert len(mesh.vertices) == 11 * 11
    assert len(mesh.faces) == 10 * 10 * 2
    assert np.allclose(mesh.vertices[:, 1], 0.0)  # flat at the origin height
    assert mesh.bounds[0][0] == -500 and mesh.bounds[1][0] == 500
    assert mesh.bounds[0][2] == -500 and mesh.bounds[1][2] == 500
    # Faces point up.
    assert (mesh.face_normals[:, 1] > 0.99).all()
    uv = mesh.visual.uv
    assert uv.min() >= 0 and uv.max() <= 1
    # Vertex 0 is the north west corner: u = 0, v = 1.
    assert np.allclose(uv[0], [0, 1])


def test_split_cells_shares_edge_points():
    runs = split_cells(10, 3)
    assert [(s.start, s.stop) for s in runs] == [(0, 4), (3, 8), (7, 11)]
    # Every cell belongs to exactly one run, and neighbors share one point.
    assert runs[0].stop - 1 == runs[1].start
    assert runs[1].stop - 1 == runs[2].start
    assert runs[-1].stop == 11


def test_split_cells_never_makes_empty_parts():
    assert len(split_cells(3, 10)) == 3
    assert len(split_cells(1, 4)) == 1
    assert split_cells(4, 1) == [slice(0, 5)]


def test_terrain_chunks_cover_the_box_without_cracks(bbox, flat_field):
    origin = (662500.0, 6473500.0, 40.0)
    whole = build_terrain(flat_field, bbox, origin, step=100.0)
    chunks = build_terrain_chunks(flat_field, bbox, origin, step=100.0, chunk_m=250.0)
    assert len(chunks) == 4 * 4
    assert sorted(chunks)[0] == "terrain_r00c00"
    # The chunks hold the same triangles as the single mesh.
    assert sum(len(m.faces) for m in chunks.values()) == len(whole.faces)
    # The corners of the whole box are still there.
    lo = np.min([m.bounds[0] for m in chunks.values()], axis=0)
    hi = np.max([m.bounds[1] for m in chunks.values()], axis=0)
    assert lo[0] == -500 and hi[0] == 500 and lo[2] == -500 and hi[2] == 500
    # Chunk r00c00 is the north west corner, so its UV reaches (0, 1).
    uv = chunks["terrain_r00c00"].visual.uv
    assert np.allclose(uv.min(axis=0), [0.0, 0.8])
    assert np.allclose(uv.max(axis=0), [0.2, 1.0])
    # Chunk r03c03 is the south east corner and reaches (1, 0).
    uv = chunks["terrain_r03c03"].visual.uv
    assert np.allclose(uv.max(axis=0), [1.0, 0.2])


def test_terrain_chunks_off_gives_one_mesh(bbox, flat_field):
    chunks = build_terrain_chunks(flat_field, bbox, (662500.0, 6473500.0, 40.0), 100.0, 0.0)
    assert list(chunks) == ["terrain"]
