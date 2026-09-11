import numpy as np

from fpv_maps.terrain import HeightField, build_terrain, fill_nodata


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
