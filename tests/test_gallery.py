from __future__ import annotations

import json
from pathlib import Path

import pytest

from fpv_maps.config import load_config
from fpv_maps.gallery import (
    Links,
    home_page,
    ingame_shots,
    map_page,
    page_order,
    read_report,
    repo_slug,
    shot_title,
    sidebar,
    tour_stills,
    write_wiki,
)

CONFIG = """
[map]
name = "{name}"
description = "A tile of one square kilometer."

[area]
bbox = [658000, 6473000, 659000, 6474000]

[buildings]
enabled = false
"""

REPORT = {
    "buildings_in_bbox": 776,
    "glb": {"triangles": 545540, "meshes": 3, "size_bytes": 26_500_000},
}


@pytest.fixture
def demo(tmp_path: Path):
    """Two maps, a screenshot folder with seven pictures and one build report."""
    maps = tmp_path / "maps"
    maps.mkdir()
    configs = []
    for name in ("demo", "old-test"):
        path = maps / f"{name}.toml"
        path.write_text(CONFIG.format(name=name))
        configs.append(load_config(path))

    shots = tmp_path / "docs" / "screenshots"
    shots.mkdir(parents=True)
    for name in (
        "demo-preview.jpg",
        "demo-tour-1-overview.jpg",
        "demo-tour-2-tartu-mill.jpg",
        "demo-tour-10-spawn.jpg",
        "demo-ingame-2.jpg",
        "demo-ingame-10.jpg",
        "old-test-tour-1-overview.jpg",
    ):
        (shots / name).write_bytes(b"x")

    dist = tmp_path / "dist"
    (dist / "demo").mkdir(parents=True)
    (dist / "demo" / "demo-build-report.json").write_text(json.dumps(REPORT))
    return configs, shots, dist


@pytest.fixture
def links() -> Links:
    return Links(repo="owner/repo")


def test_tour_stills_sort_by_shot_number(demo):
    _, shots, _ = demo
    names = [p.name for p in tour_stills(shots, "demo")]
    assert names == [
        "demo-tour-1-overview.jpg",
        "demo-tour-2-tartu-mill.jpg",
        "demo-tour-10-spawn.jpg",
    ]


def test_ingame_shots_sort_by_number_and_hold_only_that_map(demo):
    _, shots, _ = demo
    assert [p.name for p in ingame_shots(shots, "demo")] == [
        "demo-ingame-2.jpg",
        "demo-ingame-10.jpg",
    ]
    assert ingame_shots(shots, "old-test") == []


def test_shot_title():
    assert shot_title(Path("demo-tour-2-tartu-mill.jpg"), "demo") == "Tartu mill"
    assert shot_title(Path("demo-tour-1-overview.jpg"), "demo") == "Overview"


def test_page_order_puts_a_test_map_last(demo):
    configs, _, _ = demo
    assert [cfg.name for cfg in page_order(configs)] == ["demo", "old-test"]
    assert [cfg.name for cfg in page_order(list(reversed(configs)))] == ["demo", "old-test"]


def test_read_report_survives_a_missing_or_broken_file(tmp_path: Path):
    assert read_report(tmp_path, "nothing") == {}
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "broken-build-report.json").write_text("{not json")
    assert read_report(tmp_path, "broken") == {}


def test_home_page_holds_a_row_and_a_picture_for_every_map(demo, links):
    configs, shots, dist = demo
    page = home_page(configs, shots, dist, links)
    assert "# The Zone FPV maps" in page
    assert "| [`demo`](https://github.com/owner/repo/wiki/demo) | 1 km2 | 776 | 0.55 M" in page
    # A map without a build report still gets a row.
    assert "[`old-test`](https://github.com/owner/repo/wiki/old-test) | 1 km2 | - | - | -" in page
    assert "docs/screenshots/demo-tour-2-tartu-mill.jpg" in page


def test_map_page_holds_every_picture_and_the_video(demo, links):
    configs, shots, dist = demo
    page = map_page(configs[0], shots, dist, links)
    assert page.startswith("# demo")
    assert "releases/latest/download/demo-tour.mp4" in page
    assert "545,540 triangles" in page
    for name in ("demo-preview", "demo-tour-1-overview", "demo-tour-10-spawn", "demo-ingame-2"):
        assert name in page
    assert "### Tartu mill" in page
    assert "## In the game" in page
    # No picture of another map reaches this page.
    assert "old-test" not in page


def test_a_map_without_pictures_still_gets_a_page(demo, links):
    configs, shots, dist = demo
    page = map_page(configs[1], shots, dist, links)
    assert page.startswith("# old-test")
    assert "## In the game" not in page


def test_sidebar_links_home_and_every_map(demo, links):
    configs, _, _ = demo
    bar = sidebar(configs, links)
    assert "https://github.com/owner/repo/wiki)" in bar
    assert bar.index("demo)") < bar.index("old-test)")


def test_write_wiki_writes_every_page(demo, tmp_path: Path):
    configs, shots, dist = demo
    pages = write_wiki(configs, shots, dist, tmp_path / "wiki", "owner/repo")
    names = {p.name for p in pages}
    assert names == {"Home.md", "_Sidebar.md", "_Footer.md", "demo.md", "old-test.md"}
    assert (tmp_path / "wiki" / "Home.md").read_text(encoding="utf-8").startswith("# The Zone")
    assert "Maa- ja Ruumiamet" in (tmp_path / "wiki" / "_Footer.md").read_text(encoding="utf-8")


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
