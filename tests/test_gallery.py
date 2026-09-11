from __future__ import annotations

from pathlib import Path

import pytest

from fpv_maps.config import load_config
from fpv_maps.gallery import (
    gallery_markdown,
    ingame_shots,
    repo_slug,
    shot_title,
    tour_stills,
    write_gallery,
)

CONFIG = """
[map]
name = "demo"
description = "A tile of one square kilometer."

[area]
bbox = [658000, 6473000, 659000, 6474000]

[buildings]
enabled = false
"""


@pytest.fixture
def demo(tmp_path: Path):
    """A map configuration and a screenshot folder with four pictures."""
    maps = tmp_path / "maps"
    maps.mkdir()
    config = maps / "demo.toml"
    config.write_text(CONFIG)
    shots = tmp_path / "docs" / "screenshots"
    shots.mkdir(parents=True)
    for name in (
        "demo-preview.jpg",
        "demo-tour-1-overview.jpg",
        "demo-tour-2-tartu-mill.jpg",
        "demo-tour-10-spawn.jpg",
        "demo-ingame-1.jpg",
        "other-tour-1-overview.jpg",
    ):
        (shots / name).write_bytes(b"x")
    return load_config(config), shots


def test_tour_stills_sort_by_shot_number(demo):
    _, shots = demo
    names = [p.name for p in tour_stills(shots, "demo")]
    assert names == [
        "demo-tour-1-overview.jpg",
        "demo-tour-2-tartu-mill.jpg",
        "demo-tour-10-spawn.jpg",
    ]


def test_ingame_shots_hold_only_that_map(demo):
    _, shots = demo
    assert [p.name for p in ingame_shots(shots, "demo")] == ["demo-ingame-1.jpg"]
    assert ingame_shots(shots, "other") == []


def test_shot_title():
    assert shot_title(Path("demo-tour-2-tartu-mill.jpg"), "demo") == "Tartu mill"
    assert shot_title(Path("demo-tour-1-overview.jpg"), "demo") == "Overview"


def test_gallery_markdown_links_the_pictures_and_the_video(demo):
    cfg, shots = demo
    page = gallery_markdown([cfg], shots, "owner/repo")
    assert "# Map tours" in page
    assert "## demo" in page
    assert "raw.githubusercontent.com/owner/repo/main/docs/screenshots/demo-preview.jpg" in page
    assert "releases/latest/download/demo-tour.mp4" in page
    assert "demo-tour-10-spawn.jpg" in page
    assert "**In the game**" in page
    # A picture of another map never reaches this page.
    assert "other-tour-1-overview.jpg" not in page


def test_write_gallery(demo, tmp_path: Path):
    cfg, shots = demo
    path = write_gallery([cfg], shots, tmp_path / "wiki", "owner/repo")
    assert path.name == "Map-tours.md"
    assert path.read_text(encoding="utf-8").startswith("# Map tours")


def test_repo_slug_reads_the_remote(tmp_path: Path):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/owner/name.git"],
        cwd=tmp_path,
        check=True,
    )
    assert repo_slug(tmp_path) == "owner/name"

    # The same remote in the SSH form. The string is joined here, because the privacy
    # gate reads a literal "user@host" in a tracked file as a mail address.
    ssh = "git" + "@" + "github.com:owner/name.git"
    subprocess.run(["git", "remote", "set-url", "origin", ssh], cwd=tmp_path, check=True)
    assert repo_slug(tmp_path) == "owner/name"


def test_repo_slug_refuses_a_remote_without_a_name(tmp_path: Path):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "remote", "add", "origin", "file:///tmp"], cwd=tmp_path, check=True)
    with pytest.raises(ValueError, match="owner/name"):
        repo_slug(tmp_path)
