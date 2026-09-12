from pathlib import Path

from fpv_maps.buildings import build_building_meshes, read_obj
from fpv_maps.export import write_glb
from fpv_maps.inspect import inspect_glb
from fpv_maps.materials import checker_image, jpeg_image, srgb_to_linear, texture_material
from fpv_maps.preview import render_preview
from fpv_maps.probes import build_probes
from fpv_maps.terrain import build_terrain
from tests.test_buildings import OBJ


def test_export_roundtrip(tmp_path: Path, bbox, flat_field):
    import numpy as np

    origin = (662500.0, 6473500.0, 40.0)
    terrain = build_terrain(flat_field, bbox, origin, step=250.0)
    rgb = np.zeros((64, 64, 3), dtype=np.uint8)
    rgb[..., 1] = 120
    terrain.visual.material = texture_material("fpv_ground", jpeg_image(rgb, 80))

    obj = tmp_path / "x.obj"
    obj.write_text(OBJ)
    buildings = build_building_meshes(
        read_obj(obj, offset=(662500.0, 6473500.0, 40.0)),
        origin,
        "z_concrete2",
        "z_pebbled_asphalt",
    )
    meshes = {"terrain": terrain, **{f"buildings_{k}": v for k, v in buildings.items()}}
    meshes.update(build_probes(lambda x, z: 0.0))

    out = tmp_path / "t.glb"
    size = write_glb(meshes, out)
    assert size == out.stat().st_size

    stats = inspect_glb(out)
    assert stats.meshes == len(meshes)
    assert "terrain" in stats.node_names and "probe_wire-col" in stats.node_names
    assert stats.suffixes == {"-col": 1}
    assert set(stats.image_mime_types) == {"image/jpeg", "image/png"}
    assert {"fpv_ground", "z_concrete2", "z_pebbled_asphalt", "z_rough-brick1"} <= set(
        stats.material_names
    )
    assert stats.triangles > 0
    assert stats.bounds_min[0] == -500 and stats.bounds_max[0] == 500


def test_preview_image(tmp_path: Path, bbox):
    import numpy as np

    origin = (662500.0, 6473500.0, 40.0)
    ground = np.zeros((32, 32, 3), dtype=np.uint8)
    obj = tmp_path / "x.obj"
    obj.write_text(OBJ)
    roofs = build_building_meshes(read_obj(obj, offset=origin), origin, "z_a", "z_b")["roofs"]
    out = render_preview(ground, [roofs], bbox, origin, tmp_path / "p.jpg", size_px=200)
    from PIL import Image

    with Image.open(out) as img:
        assert img.size == (200, 200)
        red = np.asarray(img.convert("RGB"))[..., 0]
        # The 10 m box sits at the origin, which is the center pixel of the box.
        assert red[97:103, 98:104].max() > 50
        # The ground stays black.
        assert red[:80, :80].max() < 20


def test_preview_without_roofs(tmp_path: Path, bbox):
    import numpy as np

    ground = np.zeros((16, 16, 3), dtype=np.uint8)
    out = render_preview(
        ground, [], bbox, (662500.0, 6473500.0, 40.0), tmp_path / "p.jpg", size_px=120
    )
    assert out.exists()


def test_srgb_to_linear():
    assert srgb_to_linear(0) == 0.0
    assert srgb_to_linear(255) == 1.0
    assert abs(srgb_to_linear(128) - 0.2158) < 1e-3


def test_checker_is_png():
    assert checker_image().format == "PNG"


def read_gltf_attribute(glb: Path, mesh_name: str, attribute: str):
    """One accessor of one mesh, read from the bytes of the file.

    No trimesh. trimesh flips V on import as well as on export, so loading the file
    with it cancels the very fault these tests exist to catch.
    """
    import json
    import struct

    import numpy as np

    raw = glb.read_bytes()
    json_len = struct.unpack_from("<I", raw, 12)[0]
    js = json.loads(raw[20 : 20 + json_len])
    body = 20 + json_len + 8
    mesh = next(m for m in js["meshes"] if m.get("name") == mesh_name)
    index = mesh["primitives"][0]["attributes"][attribute]
    acc = js["accessors"][index]
    view = js["bufferViews"][acc["bufferView"]]
    dtype = {5121: "u1", 5123: "<u2", 5125: "<u4", 5126: "<f4"}[acc["componentType"]]
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[acc["type"]]
    start = body + view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    flat = np.frombuffer(raw, dtype=dtype, count=acc["count"] * width, offset=start)
    return flat.reshape(acc["count"], width)


def test_the_exported_ground_uv_follows_gltf(tmp_path: Path, bbox, flat_field):
    """North in the ground texture must land on the north edge of the exported map.

    glTF reads V = 0 from row 0 of the image, and row 0 of the orthophoto is north, so
    the north edge of the terrain must carry V = 0 in the file.

    This reads the bytes of the file. An earlier version of this test loaded the file
    with trimesh and passed for two releases while every shipped map was mirrored
    north to south, because trimesh flips V on import exactly as it flips it on
    export. A test that goes through trimesh cannot see a trimesh convention fault,
    the same way the older test that drew the map could not see it either.
    """
    import numpy as np

    origin = (662500.0, 6473500.0, 40.0)
    terrain = build_terrain(flat_field, bbox, origin, step=250.0)
    rgb = np.zeros((64, 64, 3), dtype=np.uint8)
    terrain.visual.material = texture_material("fpv_ground", jpeg_image(rgb, 80))
    glb = tmp_path / "ground.glb"
    write_glb({"terrain": terrain}, glb)

    vertices = read_gltf_attribute(glb, "terrain", "POSITION")
    uv = read_gltf_attribute(glb, "terrain", "TEXCOORD_0")
    # Game axes put north at -z, so the smallest z is the north edge of the map.
    north = vertices[:, 2] == vertices[:, 2].min()
    south = vertices[:, 2] == vertices[:, 2].max()
    assert uv[north, 1].max() < 0.01, "the north edge must read row 0 of the ground texture"
    assert uv[south, 1].min() > 0.99, "the south edge must read the last row"


def test_the_exporter_hands_gltf_v_to_the_file(tmp_path: Path):
    """Any textured mesh, not only the terrain, keeps glTF V in the file.

    The survey mesh takes its texture coordinates straight from 3D Tiles, which are
    already glTF V. They must arrive in the file unchanged.
    """
    import numpy as np
    import trimesh

    v = np.array([[0, 0, 0], [1, 0, 0], [0, 0, 1], [1, 0, 1]], dtype=float)
    uv = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    mesh = trimesh.Trimesh(vertices=v, faces=np.array([[0, 2, 1], [1, 2, 3]]), process=False)
    mesh.visual = trimesh.visual.TextureVisuals(
        uv=uv.copy(),
        material=texture_material("t", jpeg_image(np.zeros((8, 8, 3), dtype=np.uint8), 80)),
    )
    glb = tmp_path / "q.glb"
    write_glb({"quad": mesh}, glb)
    assert np.allclose(read_gltf_attribute(glb, "quad", "TEXCOORD_0"), uv)
