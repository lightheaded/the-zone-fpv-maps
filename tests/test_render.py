"""Tests of the offscreen renderer.

Every test that draws needs an OpenGL 3.3 context. A machine without one skips them,
so the suite still runs on a build agent with no GPU driver.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from fpv_maps.buildings import build_building_meshes, read_obj
from fpv_maps.export import write_glb
from fpv_maps.materials import jpeg_image, texture_material
from fpv_maps.render import (
    ground_from_geometries,
    horizon_plane,
    load_geometries,
    safe_name,
    tall_points,
)
from fpv_maps.terrain import build_terrain
from fpv_maps.tour import Shot, Tour
from tests.test_buildings import OBJ

ORIGIN = (662500.0, 6473500.0, 40.0)


@pytest.fixture(scope="session")
def opengl():
    """Skip the test when this machine has no offscreen OpenGL 3.3 context.

    It asks for the context the same way as the renderer, so that a machine with EGL
    and no display runs these tests instead of skipping them.
    """
    pytest.importorskip("moderngl")
    from fpv_maps.render import _context

    try:
        ctx = _context()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no offscreen OpenGL 3.3 context: {exc}")
    ctx.release()
    return True


@pytest.fixture
def small_glb(tmp_path: Path, bbox, flat_field) -> Path:
    """A map of one terrain tile, one building and a green ground texture."""
    terrain = build_terrain(flat_field, bbox, ORIGIN, step=250.0)
    rgb = np.zeros((64, 64, 3), dtype=np.uint8)
    rgb[..., 1] = 160
    terrain.visual.material = texture_material("fpv_ground", jpeg_image(rgb, 80))
    obj = tmp_path / "x.obj"
    obj.write_text(OBJ)
    parts = build_building_meshes(
        read_obj(obj, offset=ORIGIN), ORIGIN, "z_concrete2", "z_pebbled_asphalt"
    )
    meshes = {"terrain": terrain, **{f"buildings_{k}": v for k, v in parts.items()}}
    out = tmp_path / "small.glb"
    write_glb(meshes, out)
    return out


def test_safe_name():
    assert safe_name("Tartu Mill") == "tartu-mill"
    assert safe_name("  ") == "shot"
    assert safe_name("A/B_1") == "a-b-1"


def test_load_geometries_reads_the_texture_and_the_materials(small_glb: Path):
    geometries, bounds = load_geometries(small_glb)
    names = {g.name for g in geometries}
    assert {"terrain", "buildings_walls", "buildings_roofs"} <= names
    terrain = next(g for g in geometries if g.name == "terrain")
    walls = next(g for g in geometries if g.name == "buildings_walls")
    roofs = next(g for g in geometries if g.name == "buildings_roofs")
    assert terrain.texture is not None and not terrain.flat
    assert walls.texture is None and walls.flat
    # A concrete wall is lighter than an asphalt roof, so a picture shows the shape.
    assert sum(walls.color) > sum(roofs.color)
    assert bounds.shape == (2, 3)


def test_load_geometries_needs_a_mesh(small_glb: Path, monkeypatch):
    import trimesh

    monkeypatch.setattr(trimesh, "load", lambda *a, **k: trimesh.Scene())
    with pytest.raises(ValueError, match="no mesh"):
        load_geometries(small_glb)


def test_tall_points_find_the_building(small_glb: Path):
    geometries, _ = load_geometries(small_glb)
    ground = ground_from_geometries(geometries)
    points = tall_points(geometries, ground, count=2)
    assert points
    x, z, height = points[0]
    assert abs(x) < 30 and abs(z) < 30
    assert 4.0 <= height < 30.0


def test_the_horizon_plane_lies_below_the_terrain(small_glb: Path):
    geometries, bounds = load_geometries(small_glb)
    ground = ground_from_geometries(geometries)
    plane = horizon_plane(bounds, ground)
    assert plane.positions[:, 1].max() < float(ground.grid.min())
    assert np.ptp(plane.positions[:, 0]) > 10000


def test_render_draws_the_sky_over_the_ground(opengl, small_glb: Path):
    from fpv_maps.render import SceneRenderer
    from fpv_maps.tour import Pose

    tour = Tour(name="small", shots=(), width=160, height=90)
    with SceneRenderer(small_glb, tour) as renderer:
        pixels = renderer.render(Pose(eye=(0.0, 60.0, 300.0), look=(0.0, 5.0, 0.0), fov_deg=45.0))
    assert pixels.shape == (90, 160, 3)
    sky = pixels[:6].mean(axis=(0, 1))
    ground = pixels[-6:].mean(axis=(0, 1))
    assert sky[2] > sky[0], "the sky is blue"
    assert ground[1] > ground[2], "the ground texture is green"


def test_write_tour_writes_the_stills_and_the_video(opengl, small_glb: Path, tmp_path: Path):
    from fpv_maps.render import write_tour

    tour = Tour(
        name="small",
        shots=(
            Shot(name="one", kind="orbit", seconds=0.5, target=(0.0, 0.0), radius_m=200.0),
            Shot(name="two", kind="orbit", seconds=0.5, target=(0.0, 0.0), radius_m=150.0),
        ),
        fps=8,
        width=160,
        height=90,
        still_px=160,
    )
    seen: list[tuple[int, int]] = []
    result = write_tour(
        small_glb, tour, tmp_path / "tour", on_frame=lambda a, b: seen.append((a, b))
    )
    assert result.frames == 8
    assert seen[-1] == (8, 8)
    assert [p.name for p in result.stills] == [
        "small-tour-1-one.jpg",
        "small-tour-2-two.jpg",
    ]
    assert all(p.stat().st_size > 0 for p in result.stills)
    assert result.video is not None and result.video.stat().st_size > 0


def test_write_tour_renders_one_shot(opengl, small_glb: Path, tmp_path: Path):
    from fpv_maps.render import write_tour

    tour = Tour(
        name="small",
        shots=(
            Shot(name="one", kind="orbit", seconds=0.5, target=(0.0, 0.0)),
            Shot(name="two", kind="orbit", seconds=0.5, target=(0.0, 0.0)),
        ),
        fps=4,
        width=160,
        height=90,
    )
    result = write_tour(small_glb, tour, tmp_path / "t", only="two", video=False)
    assert result.frames == 2
    assert result.video is None
    assert [p.name for p in result.stills] == ["small-tour-1-two.jpg"]
    with pytest.raises(ValueError, match="no shot is named"):
        write_tour(small_glb, tour, tmp_path / "t", only="three", video=False)


def test_write_tour_falls_back_to_the_automatic_tour(opengl, small_glb: Path, tmp_path: Path):
    from fpv_maps.render import write_tour

    tour = Tour(name="small", shots=(), fps=2, width=160, height=90)
    result = write_tour(small_glb, tour, tmp_path / "auto", video=False)
    assert len(result.stills) >= 2
    assert result.stills[0].name.endswith("-1-overview.jpg")


def test_the_ground_texture_is_not_mirrored(opengl, tmp_path: Path, bbox, flat_field):
    """North in the source array must stay north in the picture.

    glTF counts the texture rows from the top and OpenGL counts them from the bottom.
    Without the flip in the upload the whole ground texture is mirrored north to south.
    """
    from fpv_maps.render import SceneRenderer
    from fpv_maps.tour import Pose

    rgb = np.zeros((64, 64, 3), dtype=np.uint8)
    rgb[:32, :, 0] = 220  # The north half of the source array is red.
    rgb[32:, :, 2] = 220  # The south half is blue.
    terrain = build_terrain(flat_field, bbox, ORIGIN, step=250.0)
    terrain.visual.material = texture_material("fpv_ground", jpeg_image(rgb, 90))
    glb = tmp_path / "halves.glb"
    write_glb({"terrain": terrain}, glb)

    tour = Tour(name="halves", shots=(), width=120, height=120)
    with SceneRenderer(glb, tour) as renderer:
        # Straight down from the map origin. Up in the picture is north, which is -z.
        pixels = renderer.render(Pose(eye=(0.0, 300.0, 0.0), look=(0.0, 0.0, 1.0), fov_deg=60.0))
    north = pixels[:40].reshape(-1, 3).mean(axis=0)
    south = pixels[-40:].reshape(-1, 3).mean(axis=0)
    assert north[0] > north[2], "the north half is red"
    assert south[2] > south[0], "the south half is blue"
