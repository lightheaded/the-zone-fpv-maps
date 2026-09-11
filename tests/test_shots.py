from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

from fpv_maps.shots import clean_image, collect, import_shots, next_number


def make_png(path: Path, size: tuple[int, int] = (3200, 1800), age: float = 0.0) -> Path:
    """A picture with EXIF style metadata and a modification time ``age`` seconds old."""
    image = Image.new("RGB", size, (40, 90, 160))
    image.info["comment"] = "camera, user name, machine name"
    image.save(path, format="PNG")
    if age:
        stamp = path.stat().st_mtime - age
        os.utime(path, (stamp, stamp))
    return path


def test_collect_sorts_the_oldest_first(tmp_path: Path):
    new = make_png(tmp_path / "b.png", (40, 20))
    old = make_png(tmp_path / "a.png", (40, 20), age=600)
    assert collect([tmp_path]) == [old, new]
    assert collect([new]) == [new]


def test_collect_refuses_a_file_that_is_not_a_picture(tmp_path: Path):
    other = tmp_path / "notes.txt"
    other.write_text("hello")
    with pytest.raises(ValueError, match="not a picture"):
        collect([other])


def test_clean_image_scales_and_drops_the_metadata(tmp_path: Path):
    source = make_png(tmp_path / "s.png", (3200, 1800))
    image = clean_image(source, width=1600)
    assert image.size == (1600, 900)
    assert not image.info


def test_import_shots_names_the_pictures(tmp_path: Path):
    make_png(tmp_path / "one.png", (800, 450), age=600)
    make_png(tmp_path / "two.png", (800, 450))
    out = tmp_path / "docs"
    written = import_shots([tmp_path], "vaksali", out, width=400)
    assert [p.name for p in written] == ["vaksali-ingame-1.jpg", "vaksali-ingame-2.jpg"]
    with Image.open(written[0]) as image:
        assert image.size == (400, 225)
        assert image.format == "JPEG"
        assert "exif" not in image.info


def test_import_shots_can_add_to_a_map_that_has_pictures(tmp_path: Path):
    source = tmp_path / "raw"
    source.mkdir()
    make_png(source / "one.png", (800, 450))
    out = tmp_path / "docs"
    import_shots([source], "ulejoe", out, width=200)
    again = import_shots([source], "ulejoe", out, width=200, start=next_number(out, "ulejoe"))
    assert [p.name for p in again] == ["ulejoe-ingame-2.jpg"]
    assert next_number(out, "ulejoe") == 3
    assert next_number(out, "other") == 1
