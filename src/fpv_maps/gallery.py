"""Generate the pages of the project wiki.

The wiki is the picture house of the project. `docs/maps.md` holds the facts and must
stay readable in a pull request, so it carries two pictures per map. The wiki carries
every picture, and it links the tour video of the newest release.

The generator writes four kinds of page:

- ``Home.md``, the index: what the project is, and a table of every map.
- ``<name>.md``, one page per map, with every picture of that map.
- ``_Sidebar.md``, the navigation of every page.
- ``_Footer.md``, the attribution and the note that a machine writes these pages.

Every picture is linked from the repository, so the wiki holds no second copy that can
age. Nobody must edit these pages in the wiki, because the next run replaces them.
``scripts/publish-tours.sh`` writes them and pushes them.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from fpv_maps.config import MapConfig

HOME = "Home.md"
SIDEBAR = "_Sidebar.md"
FOOTER = "_Footer.md"
LICENSE_PAGE = "https://geoportaal.maaruum.ee/"


def repo_slug(cwd: Path | None = None) -> str:
    """The ``owner/name`` of the origin remote, for a raw file link."""
    url = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    match = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url)
    if not match:
        raise ValueError(f"cannot read owner/name from the remote {url!r}")
    return match.group(1)


def tour_stills(screenshots: Path, name: str) -> list[Path]:
    """Every tour picture of one map, in shot order."""

    def number(path: Path) -> int:
        tail = path.stem.split("-tour-")[-1].split("-")[0]
        return int(tail) if tail.isdigit() else 0

    return sorted(screenshots.glob(f"{name}-tour-*.jpg"), key=number)


def ingame_shots(screenshots: Path, name: str) -> list[Path]:
    """Every in-game screenshot of one map, in number order."""

    def number(path: Path) -> int:
        tail = path.stem.rsplit("-", 1)[-1]
        return int(tail) if tail.isdigit() else 0

    return sorted(screenshots.glob(f"{name}-ingame-*.jpg"), key=number)


def shot_title(path: Path, name: str) -> str:
    """A readable title from a file name, for example "Tartu mill"."""
    tail = path.stem.replace(f"{name}-tour-", "")
    words = tail.split("-", 1)[-1].replace("-", " ")
    return words[:1].upper() + words[1:]


def read_report(dist: Path, name: str) -> dict:
    """The build report of a map, or an empty dictionary when there is none."""
    path = dist / name / f"{name}-build-report.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


@dataclass(frozen=True)
class Links:
    """Where the wiki points: the repository, the raw pictures and the releases."""

    repo: str
    branch: str = "main"

    @property
    def project(self) -> str:
        return f"https://github.com/{self.repo}"

    @property
    def raw(self) -> str:
        return f"https://raw.githubusercontent.com/{self.repo}/{self.branch}/docs/screenshots"

    @property
    def releases(self) -> str:
        return f"{self.project}/releases"

    def video(self, name: str) -> str:
        return f"{self.releases}/latest/download/{name}-tour.mp4"

    def page(self, name: str) -> str:
        return f"{self.project}/wiki/{name}"

    def picture(self, path: Path, title: str) -> str:
        """A picture that opens in full size when a reader clicks it."""
        return f"[![{title}]({self.raw}/{path.name})]({self.raw}/{path.name})"


def page_order(maps: list[MapConfig]) -> list[MapConfig]:
    """The reading order of the maps: the maps to fly first, a test map last."""
    return sorted(maps, key=lambda cfg: (cfg.name.endswith("-test"), cfg.name))


def home_page(maps: list[MapConfig], screenshots: Path, dist: Path, links: Links) -> str:
    """The index page: what the project is, one row per map, and one picture per map."""
    maps = page_order(maps)
    lines = [
        "# The Zone FPV maps",
        "",
        "Maps of real places for [The Zone](https://store.steampowered.com/app/3491280/),"
        " built from Estonian open",
        f"geodata by the pipeline in [{links.repo}]({links.project})."
        " This wiki is the picture house:",
        "every map has a page with its whole camera tour. The facts live in the repository.",
        "",
        "| Map | Area | Buildings | Triangles | File | Pictures |",
        "|-----|------|-----------|-----------|------|----------|",
    ]
    for cfg in maps:
        report = read_report(dist, cfg.name)
        glb = report.get("glb", {})
        buildings = report.get("buildings_in_bbox")
        triangles = glb.get("triangles")
        size = glb.get("size_bytes")
        pictures = len(tour_stills(screenshots, cfg.name)) + len(
            ingame_shots(screenshots, cfg.name)
        )
        cells = [
            f"[`{cfg.name}`]({links.page(cfg.name)})",
            f"{cfg.area_km2:.0f} km2",
            f"{buildings:,}" if buildings else "-",
            f"{triangles / 1e6:.2f} M" if triangles else "-",
            f"{size / 1e6:.0f} MB" if size else "-",
            str(pictures),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "## One picture of each", ""]
    for cfg in maps:
        stills = tour_stills(screenshots, cfg.name)
        preview = screenshots / f"{cfg.name}-preview.jpg"
        best = stills[1] if len(stills) > 1 else (stills[0] if stills else None)
        if best is None and preview.is_file():
            best = preview
        if best is None:
            continue
        lines += [
            f"**[{cfg.name}]({links.page(cfg.name)})**",
            "",
            f"[![{cfg.name}]({links.raw}/{best.name})]({links.page(cfg.name)})",
            "",
        ]
    lines += [
        "## Where every picture comes from",
        "",
        "A map carries three kinds of picture.",
        "",
        "- **The preview** is the ground texture from above, with every roof marked red.",
        "  The build writes it.",
        "- **The tour** comes from `fpv-maps tour`. It flies a camera over the built glTF",
        "  file and renders the frames offline. The geometry, the ground texture and the",
        "  spawn point are the true ones. There is no shadow, no vegetation and no in-game",
        "  material, so a tour picture shows the shape of a map, not the look of a flight.",
        "- **The in-game picture** comes from a person who flies the map. The game has no",
        "  free camera and no command line option that loads a map, so no script can make",
        "  one.",
        "",
        "## Get a map",
        "",
        f"1. Download the `.glb` file of a map from the [newest release]({links.releases}/latest).",
        "2. Open the game folder of The Zone.",
        "3. Create `custom_maps/<name>/` and put `<name>.glb` in it. The folder name and the",
        "   file name must be equal.",
        "4. Start the game and open Play Offline. The map stands under the custom maps.",
        "",
        "## Read more",
        "",
        f"- [README]({links.project}#readme): what the project is and how to build a map.",
        f"- [docs/maps.md]({links.project}/blob/{links.branch}/docs/maps.md): the inventory,",
        "  with the box, the spawn point and the source data of every map.",
        f"- [docs/decisions.md]({links.project}/blob/{links.branch}/docs/decisions.md): every",
        "  decision and its reason.",
        f"- [docs/the-zone-format.md]"
        f"({links.project}/blob/{links.branch}/docs/the-zone-format.md):",
        "  what the game loads, and what the engine can do.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def map_page(cfg: MapConfig, screenshots: Path, dist: Path, links: Links) -> str:
    """One page for one map: the facts in short, then every picture."""
    report = read_report(dist, cfg.name)
    glb = report.get("glb", {})
    box = list(cfg.bbox.as_tuple())
    lines = [
        f"# {cfg.name}",
        "",
        cfg.description,
        "",
        f"- Area: {cfg.area_km2:.0f} km2. Box in L-EST97 (east, north): {box}.",
        f"- Ground texture: {cfg.ground_texture_px} px, "
        f"{cfg.bbox.width / cfg.ground_texture_px:.2f} m per pixel.",
    ]
    if report.get("buildings_in_bbox"):
        lines.append(f"- Buildings: {report['buildings_in_bbox']:,} from the LOD2 data.")
    if glb.get("triangles"):
        lines.append(
            f"- Build: {glb['triangles']:,} triangles, {glb.get('meshes', 0)} meshes, "
            f"{glb.get('size_bytes', 0) / 1e6:.1f} MB."
        )
    lines += [
        f"- [Download the map file]({links.releases}/latest), as `{cfg.name}.glb`.",
        f"- [Tour video, 1080p]({links.video(cfg.name)}), from the newest release.",
        "",
    ]

    preview = screenshots / f"{cfg.name}-preview.jpg"
    if preview.is_file():
        lines += ["## From above", "", links.picture(preview, f"{cfg.name} from above"), ""]

    stills = tour_stills(screenshots, cfg.name)
    if stills:
        lines += ["## The tour", ""]
        for still in stills:
            title = shot_title(still, cfg.name)
            lines += [f"### {title}", "", links.picture(still, title), ""]

    shots = ingame_shots(screenshots, cfg.name)
    if shots:
        lines += ["## In the game", ""]
        for shot in shots:
            lines += [links.picture(shot, f"{cfg.name} in the game"), ""]
    return "\n".join(lines).rstrip() + "\n"


def sidebar(maps: list[MapConfig], links: Links) -> str:
    """The navigation that stands beside every page."""
    lines = ["### The Zone FPV maps", "", f"- [Home]({links.project}/wiki)", "", "**Maps**", ""]
    lines += [f"- [{cfg.name}]({links.page(cfg.name)})" for cfg in page_order(maps)]
    lines += [
        "",
        "**Repository**",
        "",
        f"- [Code and docs]({links.project})",
        f"- [Releases]({links.releases})",
    ]
    return "\n".join(lines) + "\n"


def footer(links: Links) -> str:
    """The attribution and the note that a machine writes these pages."""
    return (
        f"Map data: [Maa- ja Ruumiamet]({LICENSE_PAGE}) open geodata, Estonia. "
        f"See [NOTICE]({links.project}/blob/{links.branch}/NOTICE) for the attribution. "
        "These pages are generated by `fpv-maps gallery`. Do not edit them here.\n"
    )


def write_wiki(
    maps: list[MapConfig],
    screenshots: Path,
    dist: Path,
    out_dir: Path,
    repo: str,
    branch: str = "main",
) -> list[Path]:
    """Write every wiki page into ``out_dir`` and return the paths."""
    links = Links(repo=repo, branch=branch)
    maps = page_order(maps)
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = {
        HOME: home_page(maps, screenshots, dist, links),
        SIDEBAR: sidebar(maps, links),
        FOOTER: footer(links),
    }
    for cfg in maps:
        pages[f"{cfg.name}.md"] = map_page(cfg, screenshots, dist, links)

    written: list[Path] = []
    for name, text in pages.items():
        path = out_dir / name
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written
