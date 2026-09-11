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
    cfg = load_config(Path(__file__).parent.parent / "maps" / "annelinn-test.toml")
    assert cfg.municipalities == ("Tartu_linn", "Luunja_vald")
