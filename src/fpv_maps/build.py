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
from fpv_maps.buildings import BuildingSet, build_building_chunks, read_obj, read_offset
from fpv_maps.config import MapConfig
from fpv_maps.export import write_glb
from fpv_maps.fetch import LICENSE_URL, Fetcher
from fpv_maps.geotiff import dtm_resolution, read_heights, read_rgb
from fpv_maps.inspect import inspect_glb
from fpv_maps.materials import jpeg_image, texture_material
from fpv_maps.preview import render_preview
from fpv_maps.probes import build_probes
from fpv_maps.terrain import build_terrain_chunks

console = Console()


def build_map(cfg: MapConfig, quiet: bool = False) -> Path:
    t0 = time.time()
    log = console.log if not quiet else (lambda *a, **k: None)
    report: dict = {
        "map": cfg.name,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool_version": __version__,
        "bbox_lest97": cfg.bbox.as_tuple(),
        "area_km2": round(cfg.area_km2, 2),
        "origin_lest97": cfg.origin,
        "terrain_step_m": cfg.terrain_step_m,
        "chunk_m": cfg.chunk_m,
        "ground_texture_px": cfg.ground_texture_px,
        "ground_texture_m_per_px": round(cfg.bbox.width / cfg.ground_texture_px, 3),
        "sources": [],
        "license": LICENSE_URL,
    }

    fetcher = Fetcher(cfg.data_dir, quiet=quiet)
    try:
        log(f"[bold]{cfg.name}[/] {cfg.area_km2:.0f} km2, bbox {cfg.bbox.as_tuple()}")
        dtm_paths = fetcher.fetch_dtm(cfg.bbox)
        ortho_paths = fetcher.fetch_ortho(cfg.bbox, cfg.ground_texture_source)
        report["sources"].append({"dataset": "DTM 1 m", "files": [p.name for p in dtm_paths]})
        report["sources"].append(
            {
                "dataset": f"Orthophoto, {cfg.ground_texture_source}",
                "files": [p.parent.name for p in ortho_paths],
            }
        )

        lod2_files: list[tuple[Path, Path]] = []
        if cfg.buildings_enabled:
            lod2_files = [fetcher.fetch_lod2(m) for m in cfg.municipalities]
            report["sources"].append(
                {"dataset": "3D buildings LOD2", "files": [obj.name for obj, _ in lod2_files]}
            )
    finally:
        fetcher.close()

    dtm_res = dtm_resolution(cfg.terrain_step_m, native_m=1.0)
    log(f"terrain, step {cfg.terrain_step_m} m, elevation read at {dtm_res} m")
    field = read_heights(dtm_paths, cfg.bbox, res_m=dtm_res)
    origin_h = field.sample_one(*cfg.origin)
    origin = (cfg.origin[0], cfg.origin[1], origin_h)
    report["origin_height_eh2000"] = round(origin_h, 2)
    terrain = build_terrain_chunks(field, cfg.bbox, origin, cfg.terrain_step_m, cfg.chunk_m)
    report["terrain_chunks"] = len(terrain)

    log(f"ground texture {cfg.ground_texture_px} px")
    rgb = read_rgb(ortho_paths, cfg.bbox, cfg.ground_texture_px)
    ground = texture_material("fpv_ground", jpeg_image(rgb, cfg.jpeg_quality))
    for mesh in terrain.values():
        mesh.visual.material = ground

    meshes: dict[str, trimesh.Trimesh] = dict(terrain)

    if lod2_files:
        log("buildings")
        buildings = BuildingSet()
        for obj_path, fwt_path in lod2_files:
            buildings.extend(read_obj(obj_path, read_offset(fwt_path)).inside(cfg.bbox))
        report["buildings_in_bbox"] = len(buildings)
        meshes.update(
            build_building_chunks(
                buildings,
                cfg.bbox,
                origin,
                cfg.wall_material,
                cfg.roof_material,
                cfg.chunk_m,
            )
        )

    if cfg.probes_enabled:
        log("probes")

        def ground_height(x: float, z: float) -> float:
            return field.sample_one(origin[0] + x, origin[1] - z) - origin[2]

        meshes.update(build_probes(ground_height))

    out = cfg.dist_dir / f"{cfg.name}.glb"
    log(f"export {out}, {len(meshes)} meshes")
    size = write_glb(meshes, out)
    log("preview")
    render_preview(
        rgb,
        [m for name, m in meshes.items() if name.endswith("_roofs")],
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
