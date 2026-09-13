from pathlib import Path

import pytest

from fpv_maps.config import load_config

MINIMAL = """
[map]
name = "test"

[area]
bbox = [662000, 6473000, 663000, 6474000]
"""


def test_buildings_need_municipalities(tmp_path):
    path = tmp_path / "test.toml"
    path.write_text(MINIMAL)
    with pytest.raises(ValueError, match="municipalities"):
        load_config(path)


def test_no_municipalities_without_buildings(tmp_path):
    path = tmp_path / "test.toml"
    path.write_text(MINIMAL + "\n[buildings]\nenabled = false\n")
    assert load_config(path).municipalities == ()


def test_map_config_lists_municipalities():
    cfg = load_config(Path(__file__).parent.parent / "maps" / "tartu-annelinn-test.toml")
    assert cfg.municipalities == ("Tartu_linn", "Luunja_vald")


def test_defaults_have_no_chunks_and_the_city_orthophoto(tmp_path):
    path = tmp_path / "test.toml"
    path.write_text(MINIMAL + "\n[buildings]\nenabled = false\n")
    cfg = load_config(path)
    assert cfg.chunk_m == 0.0
    assert cfg.ground_texture_source == "city"
    assert cfg.area_km2 == 1.0


def test_unknown_ground_texture_source(tmp_path):
    path = tmp_path / "test.toml"
    path.write_text(
        MINIMAL + '\n[buildings]\nenabled = false\n\n[ground_texture]\nsource = "moon"\n'
    )
    with pytest.raises(ValueError, match="ground_texture.source"):
        load_config(path)


def test_base_map_config():
    cfg = load_config(Path(__file__).parent.parent / "maps" / "tartu.toml")
    assert cfg.area_km2 == 81.0
    assert cfg.chunk_m == 1500.0
    assert cfg.ground_texture_source == "estonia"
    assert cfg.terrain_step_m == 10.0
    assert cfg.municipalities[0] == "Tartu_linn"
    assert len(cfg.municipalities) == 5
    # The spawn point is inside the box and not at its center.
    assert cfg.bbox.contains(*cfg.origin)
    assert cfg.origin != cfg.bbox.center


MAPS = sorted((Path(__file__).parent.parent / "maps").glob("*.toml"))


@pytest.mark.parametrize("path", MAPS, ids=lambda p: p.stem)
def test_every_map_config_is_valid(path):
    """Every file in maps/ loads, and the map name is the file name."""
    cfg = load_config(path)
    assert cfg.name == path.stem
    assert cfg.description
    assert cfg.bbox.width > 0
    assert cfg.bbox.height > 0
    # The game spawns the drone at the origin. An origin outside the box has no terrain.
    assert cfg.bbox.contains(*cfg.origin)


@pytest.mark.parametrize("path", MAPS, ids=lambda p: p.stem)
def test_every_map_has_a_preview(path):
    """The release workflow refuses a map without a preview. Fail here first.

    A private map has no published preview by design, so it is skipped.
    """
    if load_config(path).private:
        pytest.skip("a private map is never published, so it needs no preview")
    preview = path.parent.parent / "docs" / "screenshots" / f"{path.stem}-preview.jpg"
    assert preview.is_file()
    assert preview.stat().st_size > 0


NO_BUILDINGS = MINIMAL + "\n[buildings]\nenabled = false\n"


def test_no_drone_and_no_course_by_default(tmp_path):
    path = tmp_path / "test.toml"
    path.write_text(NO_BUILDINGS)
    cfg = load_config(path)
    assert not cfg.drone
    assert cfg.gates == ()
    assert cfg.terrain_sink_m == 0.0


def test_drone_paths_resolve_against_the_map_file(tmp_path):
    survey = tmp_path / "survey"
    survey.mkdir()
    (survey / "dem.tif").write_bytes(b"")
    (survey / "ortho.tif").write_bytes(b"")
    (survey / "tiles").mkdir()
    path = tmp_path / "test.toml"
    path.write_text(
        NO_BUILDINGS
        + '\n[drone]\nelevation = ["survey/dem.tif"]\northo = ["survey/ortho.tif"]\n'
        + 'mesh_tileset = "survey/tiles"\nmesh_error_m = 0.06\nmesh_texture_px = 256\n'
    )
    cfg = load_config(path)
    assert cfg.drone.elevation == (survey / "dem.tif",)
    assert cfg.drone.ortho == (survey / "ortho.tif",)
    assert cfg.drone.tileset == survey / "tiles"
    assert cfg.drone.mesh_error_m == 0.06
    assert cfg.drone.mesh_texture_px == 256


def test_a_missing_drone_file_fails_the_load(tmp_path):
    # A survey is never downloaded, so a wrong path must stop the build rather than
    # let it fall back to the open data and claim a quality it does not have.
    path = tmp_path / "test.toml"
    path.write_text(NO_BUILDINGS + '\n[drone]\nelevation = ["survey/missing.tif"]\n')
    with pytest.raises(FileNotFoundError, match="drone source is missing"):
        load_config(path)


def test_a_missing_tileset_folder_fails_the_load(tmp_path):
    path = tmp_path / "test.toml"
    path.write_text(NO_BUILDINGS + '\n[drone]\nmesh_tileset = "survey/tiles"\n')
    with pytest.raises(FileNotFoundError, match="mesh tileset is missing"):
        load_config(path)


def test_course_gates_take_the_section_defaults(tmp_path):
    path = tmp_path / "test.toml"
    path.write_text(
        NO_BUILDINGS
        + "\n[course]\nheight_m = 7.0\nsize_m = 6.0\n"
        + "\n[[course.gate]]\nat = [662100.0, 6473100.0]\n"
        + "\n[[course.gate]]\nat = [662200.0, 6473200.0]\nheight_m = 12.0\nyaw_deg = 45.0\n"
    )
    gates = load_config(path).gates
    assert len(gates) == 2
    assert gates[0].east == 662100.0 and gates[0].height_m == 7.0 and gates[0].size_m == 6.0
    assert gates[1].height_m == 12.0 and gates[1].yaw_deg == 45.0
    assert gates[1].size_m == 6.0


def test_terrain_sink_is_read(tmp_path):
    path = tmp_path / "test.toml"
    path.write_text(NO_BUILDINGS + "\n[terrain]\nstep_m = 0.5\nsink_m = 0.5\n")
    cfg = load_config(path)
    assert cfg.terrain_step_m == 0.5
    assert cfg.terrain_sink_m == 0.5


def test_the_build_module_never_imports_an_extra_at_module_level():
    """A base install must build every map that does not use an extra.

    The facade pipeline needs scipy and the renderer needs moderngl, and both are
    optional. A top level import of either makes ``fpv_maps.build`` unimportable
    without it, which breaks every map rather than the one that asked for the extra.
    That shipped once and the release workflow, which installs no extra, would have
    failed on all five maps.
    """
    source = (Path(__file__).parent.parent / "src" / "fpv_maps" / "build.py").read_text()
    header = source.split("def build_map", 1)[0]
    for extra in ("fpv_maps.facades", "moderngl", "scipy"):
        assert extra not in header, f"{extra} must be imported inside the function"
