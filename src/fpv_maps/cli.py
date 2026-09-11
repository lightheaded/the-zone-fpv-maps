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
    console.print(f"1:2000 sheets (ortho, lidar): {' '.join(sheets_for(b, 2000))}")
    console.print(f"1:10000 sheets (DTM): {' '.join(sheets_for(b, 10000))}")


@main.command()
@click.argument("config", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def fetch(config: Path) -> None:
    """Download the source data for a map into data/raw."""
    from fpv_maps.fetch import Fetcher

    cfg = load_config(config)
    fetcher = Fetcher(cfg.data_dir)
    try:
        paths = fetcher.fetch_dtm(cfg.bbox) + fetcher.fetch_ortho_city(cfg.bbox)
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
