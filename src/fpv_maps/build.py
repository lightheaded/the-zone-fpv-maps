"""Build one map from its configuration: fetch, terrain, texture, buildings, probes, export."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import trimesh
from rich.console import Console

from fpv_maps import __version__
from fpv_maps.buildings import BuildingSet, build_building_meshes, read_obj, read_offset
from fpv_maps.config import MapConfig
from fpv_maps.export import write_glb
from fpv_maps.fetch import LICENSE_URL, Fetcher
from fpv_maps.geotiff import read_heights, read_rgb
from fpv_maps.inspect import inspect_glb
from fpv_maps.materials import jpeg_image, texture_material
from fpv_maps.preview import render_preview
from fpv_maps.probes import build_probes
from fpv_maps.terrain import build_terrain

console = Console()


def build_map(cfg: MapConfig, quiet: bool = False) -> Path:
    t0 = time.time()
    log = console.log if not quiet else (lambda *a, **k: None)
    report: dict = {
        "map": cfg.name,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool_version": __version__,
        "bbox_lest97": cfg.bbox.as_tuple(),
        "origin_lest97": cfg.origin,
        "sources": [],
        "license": LICENSE_URL,
    }

    fetcher = Fetcher(cfg.data_dir, quiet=quiet)
    try:
        log(f"[bold]{cfg.name}[/] bbox {cfg.bbox.as_tuple()} origin {cfg.origin}")
        dtm_paths = fetcher.fetch_dtm(cfg.bbox)
        ortho_paths = fetcher.fetch_ortho_city(cfg.bbox)
        report["sources"].append({"dataset": "DTM 1 m", "files": [p.name for p in dtm_paths]})
        report["sources"].append(
            {"dataset": "Orthophoto, cities", "files": [p.parent.name for p in ortho_paths]}
        )

        lod2_files: list[tuple[Path, Path]] = []
        if cfg.buildings_enabled:
            lod2_files = [fetcher.fetch_lod2(m) for m in cfg.municipalities]
            report["sources"].append(
                {"dataset": "3D buildings LOD2", "files": [obj.name for obj, _ in lod2_files]}
            )
    finally:
        fetcher.close()

    log("terrain")
    field = read_heights(dtm_paths, cfg.bbox)
    origin_h = field.sample_one(*cfg.origin)
    origin = (cfg.origin[0], cfg.origin[1], origin_h)
    report["origin_height_eh2000"] = origin_h
    terrain = build_terrain(field, cfg.bbox, origin, cfg.terrain_step_m)

    log(f"ground texture {cfg.ground_texture_px} px")
    rgb = read_rgb(ortho_paths, cfg.bbox, cfg.ground_texture_px)
    terrain.visual.material = texture_material("fpv_ground", jpeg_image(rgb, cfg.jpeg_quality))

    meshes: dict[str, trimesh.Trimesh] = {"terrain": terrain}

    if lod2_files:
        log("buildings")
        buildings = BuildingSet()
        for obj_path, fwt_path in lod2_files:
            buildings.extend(read_obj(obj_path, read_offset(fwt_path)).inside(cfg.bbox))
        report["buildings_in_bbox"] = len(buildings)
        for key, mesh in build_building_meshes(
            buildings, origin, cfg.wall_material, cfg.roof_material
        ).items():
            meshes[f"buildings_{key}"] = mesh

    if cfg.probes_enabled:
        log("probes")

        def ground(x: float, z: float) -> float:
            return field.sample_one(origin[0] + x, origin[1] - z) - origin[2]

        meshes.update(build_probes(ground))

    out = cfg.dist_dir / f"{cfg.name}.glb"
    log(f"export {out}")
    size = write_glb(meshes, out)
    log("preview")
    render_preview(
        terrain,
        meshes.get("buildings_roofs"),
        cfg.bbox,
        origin,
        cfg.dist_dir / f"{cfg.name}-preview.jpg",
    )
    stats = inspect_glb(out)
    report["glb"] = {k: v for k, v in asdict(stats).items() if k not in ("node_names",)}
    report["seconds"] = round(time.time() - t0, 1)
    (cfg.dist_dir / f"{cfg.name}-build-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    log(f"done: {size / 1e6:.1f} MB, {stats.triangles:,} triangles in {report['seconds']} s")
    return out
