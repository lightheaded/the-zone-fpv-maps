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
    """The release workflow refuses a map without a preview. Fail here first."""
    preview = path.parent.parent / "docs" / "screenshots" / f"{path.stem}-preview.jpg"
    assert preview.is_file()
    assert preview.stat().st_size > 0
