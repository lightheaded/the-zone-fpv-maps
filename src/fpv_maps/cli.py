"""Command line entry point: ``fpv-maps``."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from fpv_maps import __version__
from fpv_maps.config import load_config
from fpv_maps.crs import lest97_to_wgs84

console = Console()


@click.group()
@click.version_option(__version__)
def main() -> None:
    """Build maps of real places for The Zone FPV simulator."""


@main.command()
@click.argument("config", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def area(config: Path) -> None:
    """Show the bounding box, the origin and the map sheets of a map."""
    from fpv_maps.fetch import sheets_for

    cfg = load_config(config)
    b = cfg.bbox
    console.print(f"[bold]{cfg.name}[/]  {cfg.description}")
    console.print(f"bbox L-EST97 (E, N): {b.as_tuple()}  size {b.width:.0f} x {b.height:.0f} m")
    sw = lest97_to_wgs84(b.xmin, b.ymin)
    ne = lest97_to_wgs84(b.xmax, b.ymax)
    console.print(f"bbox WGS84: SW {sw[0]:.5f}, {sw[1]:.5f}  NE {ne[0]:.5f}, {ne[1]:.5f}")
    lat, lon = lest97_to_wgs84(*cfg.origin)
    console.print(f"origin: E {cfg.origin[0]:.1f} N {cfg.origin[1]:.1f}  ({lat:.5f}, {lon:.5f})")
    from fpv_maps.fetch import ORTHO_PRODUCTS

    grid = ORTHO_PRODUCTS[cfg.ground_texture_source].grid or 2000
    ortho = sheets_for(b, grid)
    dtm = sheets_for(b, 10000)
    console.print(f"orthophoto '{cfg.ground_texture_source}', 1:{grid} grid: {len(ortho)} sheets")
    console.print(f"  {' '.join(ortho)}")
    console.print(f"DTM 1 m, 1:10000 grid: {len(dtm)} sheets")
    console.print(f"  {' '.join(dtm)}")
    if cfg.chunk_m > 0:
        rows = max(1, round(b.height / cfg.chunk_m))
        columns = max(1, round(b.width / cfg.chunk_m))
        console.print(f"chunks: {rows} x {columns} of about {cfg.chunk_m:.0f} m")


@main.command()
@click.argument("config", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def fetch(config: Path) -> None:
    """Download the source data for a map into data/raw."""
    from fpv_maps.fetch import Fetcher

    cfg = load_config(config)
    fetcher = Fetcher(cfg.data_dir)
    try:
        paths = fetcher.fetch_dtm(cfg.bbox) + fetcher.fetch_ortho(
            cfg.bbox, cfg.ground_texture_source
        )
        for municipality in cfg.municipalities if cfg.buildings_enabled else ():
            paths.extend(fetcher.fetch_lod2(municipality))
    finally:
        fetcher.close()
    for p in paths:
        console.print(f"  {p.relative_to(cfg.data_dir)}  {p.stat().st_size / 1e6:.1f} MB")


@main.command()
@click.argument("config", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--install", "do_install", is_flag=True, help="Copy the result into the game.")
def build(config: Path, do_install: bool) -> None:
    """Build the map: fetch, terrain, texture, buildings, probes, export."""
    from fpv_maps.build import build_map

    cfg = load_config(config)
    out = build_map(cfg)
    console.print(f"[green]built[/] {out}")
    if do_install:
        _install(cfg.name, out, None)


@main.command()
@click.argument("config", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--game-dir", type=click.Path(file_okay=False, path_type=Path), default=None)
def install(config: Path, game_dir: Path | None) -> None:
    """Copy a built map into <game>/custom_maps/<name>/<name>.glb."""
    cfg = load_config(config)
    glb = cfg.dist_dir / f"{cfg.name}.glb"
    if not glb.exists():
        raise click.ClickException(f"{glb} does not exist. Run 'fpv-maps build' first.")
    _install(cfg.name, glb, game_dir)


def _install(name: str, glb: Path, game_dir: Path | None) -> None:
    from fpv_maps.install import GAME_DIR_ENV, default_game_dir, install_map

    game_dir = game_dir or default_game_dir()
    if game_dir is None:
        raise click.ClickException(f"game folder not found. Set {GAME_DIR_ENV} or pass --game-dir.")
    target = install_map(glb, name, game_dir)
    console.print(f"[green]installed[/] {target}")


@main.command()
@click.argument("config", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--out", type=click.Path(file_okay=False, path_type=Path), default=None)
@click.option("--shot", default=None, help="Render one shot of the tour by name.")
@click.option("--size", default=None, help="Frame size, for example 1920x1080.")
@click.option("--fps", type=int, default=None, help="Frames per second of the video.")
@click.option("--seconds", type=float, default=None, help="Scale the tour to this length.")
@click.option("--no-video", is_flag=True, help="Write the still pictures only.")
@click.option("--publish", is_flag=True, help="Copy the stills into docs/screenshots.")
def tour(
    config: Path,
    out: Path | None,
    shot: str | None,
    size: str | None,
    fps: int | None,
    seconds: float | None,
    no_video: bool,
    publish: bool,
) -> None:
    """Render the camera tour of a built map: still pictures and a video."""
    import shutil
    from dataclasses import replace

    from rich.progress import Progress

    from fpv_maps.render import write_tour
    from fpv_maps.tour import Tour, load_tour

    cfg = load_config(config)
    glb = cfg.dist_dir / f"{cfg.name}.glb"
    if not glb.exists():
        raise click.ClickException(f"{glb} does not exist. Run 'fpv-maps build' first.")

    plan = load_tour(cfg.path, cfg.name, cfg.origin) or Tour(name=cfg.name, shots=())
    if size:
        width, _, height = size.lower().partition("x")
        plan = replace(plan, width=int(width), height=int(height))
    if fps:
        plan = replace(plan, fps=fps)
    if not plan.shots:
        console.print(
            r"[yellow]the map declares no \[tour] shots, so this is the automatic tour[/]"
        )

    out_dir = out or (cfg.dist_dir / "tour")
    with Progress(console=console, transient=True) as progress:
        task = progress.add_task(f"render {cfg.name}", total=None)

        def on_frame(done: int, total: int) -> None:
            progress.update(task, completed=done, total=total)

        result = write_tour(
            glb,
            plan,
            out_dir,
            only=shot,
            video=not no_video,
            seconds=seconds,
            on_frame=on_frame,
        )

    rate = result.frames / max(result.seconds, 0.1)
    console.print(f"[green]rendered[/] {result.frames} frames in {result.seconds} s, {rate:.0f}/s")
    for still in result.stills:
        console.print(f"  {still}")
    if result.video is not None:
        console.print(f"  {result.video}  {result.video.stat().st_size / 1e6:.1f} MB")
    if publish:
        target = cfg.path.parent.parent / "docs" / "screenshots"
        target.mkdir(parents=True, exist_ok=True)
        for still in result.stills:
            shutil.copyfile(still, target / still.name)
        console.print(f"[green]published[/] {len(result.stills)} stills into {target}")


@main.command()
@click.argument("config", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("sources", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("--width", type=int, default=1600, help="Width of the result in pixels.")
@click.option("--append", is_flag=True, help="Keep the pictures that the map has.")
def shots(config: Path, sources: tuple[Path, ...], width: int, append: bool) -> None:
    """Import in-game screenshots into docs/screenshots with the correct name.

    SOURCES are picture files or folders. The oldest picture becomes number one.
    """
    from fpv_maps.shots import import_shots, next_number

    if not sources:
        raise click.ClickException("name at least one picture file or folder")
    cfg = load_config(config)
    out_dir = cfg.path.parent.parent / "docs" / "screenshots"
    start = next_number(out_dir, cfg.name) if append else 1
    written = import_shots(sources, cfg.name, out_dir, width=width, start=start)
    if not written:
        raise click.ClickException("no picture was found")
    for path in written:
        console.print(f"  {path}  {path.stat().st_size / 1e3:.0f} kB")
    console.print(f"[green]imported[/] {len(written)} in-game screenshots of {cfg.name}")


@main.command()
@click.option("--out", type=click.Path(file_okay=False, path_type=Path), default=None)
@click.option("--repo", default=None, help="The owner/name of the repository.")
@click.option("--branch", default="main", help="The branch that holds the pictures.")
def gallery(out: Path | None, repo: str | None, branch: str) -> None:
    """Write the wiki pages: the index, one page per map, the navigation."""
    from fpv_maps.gallery import repo_slug, write_wiki

    root = Path(__file__).resolve().parent.parent.parent
    configs = sorted(root.glob("maps/*.toml"))
    if not configs:
        raise click.ClickException("maps/ holds no configuration")
    # A private map gets no wiki page. The wiki is public, and a page for such a map
    # would carry its preview and its tour pictures, which is the thing that must not
    # be published. The release workflow, publish-tours.sh and release-notes.sh skip
    # them too, and this is the fourth publisher that walks maps/ and has to.
    maps = [cfg for cfg in (load_config(path) for path in configs) if not cfg.private]
    skipped = len(configs) - len(maps)
    if skipped:
        console.print(f"[yellow]skipped[/] {skipped} private map(s): they are never published")
    out_dir = out or (root / "dist" / "wiki")
    pages = write_wiki(
        maps,
        root / "docs" / "screenshots",
        root / "dist",
        out_dir,
        repo or repo_slug(root),
        branch,
    )
    for page in pages:
        console.print(f"  {page.name}  {page.stat().st_size / 1e3:.1f} kB")
    console.print(f"[green]wrote[/] {len(pages)} wiki pages into {out_dir}")
    console.print("Push them with scripts/publish-tours.sh.")


@main.command()
@click.argument("names", nargs=-1)
@click.option("--dist", type=click.Path(file_okay=False, path_type=Path), default=Path("dist"))
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
def benchmark(names: tuple[str, ...], dist: Path, out: Path | None) -> None:
    """Collect the build reports of NAMES into one cost table.

    With no names it takes every map that has a build report, newest first. The table
    has an empty frame rate column per machine, to fill in after flying the course.
    """
    from fpv_maps.benchmark import collect, markdown_table

    if not names:
        names = tuple(sorted(p.name for p in dist.iterdir() if p.is_dir()))
    costs = collect(dist, list(names))
    if not costs:
        raise click.ClickException(f"no build report under {dist}. Run 'fpv-maps build' first.")
    table = markdown_table(costs)
    blocked = [(c.name, c.blocked_gates) for c in costs if c.blocked_gates]
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(table + "\n", encoding="utf-8")
        console.print(f"[green]wrote[/] {out}")
    else:
        click.echo(table)
    for name, gates in blocked:
        console.print(f"[bold yellow]warning[/] {name}: gates not clear: {gates}")


@main.command(name="inspect")
@click.argument("glb", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--json", "as_json", is_flag=True, help="Print the full statistics as JSON.")
def inspect_cmd(glb: Path, as_json: bool) -> None:
    """Print statistics of a glTF binary file."""
    from fpv_maps.inspect import inspect_glb

    stats = inspect_glb(glb)
    if as_json:
        click.echo(stats.to_json())
        return
    console.print(f"[bold]{glb}[/]  {stats.size_bytes / 1e6:.1f} MB  generator: {stats.generator}")
    console.print(
        f"nodes {stats.nodes}  meshes {stats.meshes}  materials {stats.materials}  "
        f"images {stats.images} ({stats.image_bytes / 1e6:.1f} MB, {stats.image_mime_types})"
    )
    console.print(f"triangles {stats.triangles:,}  vertices {stats.vertices:,}")
    console.print(f"bounds min {stats.bounds_min}  max {stats.bounds_max}")
    if stats.suffixes:
        console.print(f"Godot name suffixes: {stats.suffixes}")
    console.print(f"materials: {', '.join(stats.material_names[:40])}")


if __name__ == "__main__":
    sys.exit(main())
