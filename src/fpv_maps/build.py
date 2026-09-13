"""Build one map from its configuration: fetch, terrain, texture, buildings, probes, export."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image
from rich.console import Console

from fpv_maps import __version__
from fpv_maps.buildings import BuildingSet, build_building_chunks, read_obj, read_offset
from fpv_maps.config import MapConfig
from fpv_maps.course import build_course, check_clearance, course_length_m
from fpv_maps.drone import (
    load_mesh_tiles,
    measure_vertical_shift,
    read_drone_heights,
    read_drone_rgb,
    select_tiles,
)
from fpv_maps.export import write_glb
from fpv_maps.facades import build_facade_buildings
from fpv_maps.fetch import LICENSE_URL, Fetcher
from fpv_maps.geotiff import dtm_resolution, read_heights, read_rgb
from fpv_maps.inspect import inspect_glb
from fpv_maps.lidar import read_surface
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

    lidar_paths: list[Path] = []
    lidar_rgb = None
    if cfg.lidar.enabled:
        fetcher = Fetcher(cfg.data_dir, quiet=quiet)
        try:
            lidar_paths = fetcher.fetch_lidar(cfg.bbox)
        finally:
            fetcher.close()
        report["sources"].append(
            {"dataset": "Lidar point cloud", "files": [p.name for p in lidar_paths]}
        )

    height_shift = 0.0
    if cfg.lidar.enabled:
        # The surface the scanner saw, not the bare earth under it. The trees, the
        # roofs and the masts are the mesh here, so this map has no building model
        # and no separate wall or roof material at all.
        log(f"surface from the laser scan, {len(lidar_paths)} sheets at {cfg.lidar.res_m} m")
        field, lidar_rgb = read_surface(
            lidar_paths,
            cfg.bbox,
            cfg.lidar.res_m,
            classes=cfg.lidar.classes or None,
            colour=cfg.lidar.colour,
            close_cells=cfg.lidar.close_cells,
            smooth_cells=cfg.lidar.smooth_cells,
        )
        report["lidar"] = {
            "res_m": cfg.lidar.res_m,
            "sheets": len(lidar_paths),
            "colour_from_points": cfg.lidar.colour,
            "classes": list(cfg.lidar.classes),
            "close_cells": cfg.lidar.close_cells,
            "smooth_cells": cfg.lidar.smooth_cells,
        }
    elif cfg.drone.elevation:
        # The survey writes ellipsoidal heights and the open data writes EH2000.
        # Measure the offset against the open model, so that every height of the map
        # is EH2000 and an open data building sits on drone ground at the right level.
        height_shift = measure_vertical_shift(cfg.drone.elevation, dtm_paths, cfg.bbox)
        dtm_res = dtm_resolution(cfg.terrain_step_m, native_m=0.098)
        log(
            f"terrain from the survey, step {cfg.terrain_step_m} m, "
            f"read at {dtm_res:.3f} m, height shift {height_shift:+.2f} m to EH2000"
        )
        field = read_drone_heights(cfg.drone.elevation, cfg.bbox, res_m=dtm_res)
        field = replace(field, heights=field.heights + height_shift)
        report["sources"].append(
            {
                "dataset": "Own drone survey, elevation",
                "files": [p.name for p in cfg.drone.elevation],
            }
        )
        report["drone_height_shift_m"] = round(height_shift, 3)
    else:
        dtm_res = dtm_resolution(cfg.terrain_step_m, native_m=1.0)
        log(f"terrain, step {cfg.terrain_step_m} m, elevation read at {dtm_res} m")
        field = read_heights(dtm_paths, cfg.bbox, res_m=dtm_res)
    origin_h = field.sample_one(*cfg.origin)
    origin = (cfg.origin[0], cfg.origin[1], origin_h)
    report["origin_height_eh2000"] = round(origin_h, 2)
    # The filler terrain and the survey mesh describe the same ground twice, and the
    # two disagree by a few centimeters, so the terrain pokes through the mesh at a
    # grazing angle. Sinking the terrain a little puts it below the mesh everywhere.
    # The origin is read before the sink, so the spawn still stands on true ground and
    # only the filler outside the mesh drops.
    terrain_field = field
    if cfg.terrain_sink_m:
        terrain_field = replace(field, heights=field.heights - cfg.terrain_sink_m)
        report["terrain_sink_m"] = cfg.terrain_sink_m
    terrain = build_terrain_chunks(terrain_field, cfg.bbox, origin, cfg.terrain_step_m, cfg.chunk_m)
    report["terrain_chunks"] = len(terrain)

    log(f"ground texture {cfg.ground_texture_px} px")
    if lidar_rgb is not None:
        # The colour of the highest return in each cell, which is the colour of the
        # surface the mesh describes. It is the only texture that puts a wall colour
        # on a wall: an orthophoto looks straight down and smears the roof over it.
        rgb = np.asarray(
            Image.fromarray(lidar_rgb).resize(
                (cfg.ground_texture_px, cfg.ground_texture_px), Image.LANCZOS
            )
        )
    else:
        rgb = read_rgb(ortho_paths, cfg.bbox, cfg.ground_texture_px)
    if cfg.drone.ortho:
        # The survey covers less ground than the box, so the open orthophoto stays
        # under it and the drone pixels replace it where they exist.
        rgb = read_drone_rgb(cfg.drone.ortho, cfg.bbox, cfg.ground_texture_px, base=rgb)
        report["sources"].append(
            {
                "dataset": "Own drone survey, orthophoto",
                "files": [p.name for p in cfg.drone.ortho],
            }
        )
    report["ground_texture_m_per_px"] = round(cfg.bbox.width / cfg.ground_texture_px, 4)
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
        if cfg.facades.enabled:
            # A whole photo frame is about a kilometre across, so the camera fit needs
            # terrain well outside the map box. It is read coarse: it only carries the
            # four corners of a frame, never a triangle of the map.
            log("facades from oblique photos")
            wide = cfg.bbox.buffer(2000.0)
            fetcher = Fetcher(cfg.data_dir, quiet=quiet)
            try:
                wide_dtm = fetcher.fetch_dtm(wide)
            finally:
                fetcher.close()
            corner_field = read_heights(wide_dtm, wide, res_m=5.0)
            facade_meshes, facade_report = build_facade_buildings(
                buildings, cfg, origin, field, corner_field, rgb, ground, log=log
            )
            meshes.update(facade_meshes)
            report["facades"] = facade_report
            report["sources"].append(
                {
                    "dataset": "Oblique photos, Maa- ja Ruumiamet Fotoladu",
                    "files": [p["image"] for p in facade_report["photos"]],
                }
            )
        else:
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

    def ground_height(x: float, z: float) -> float:
        return field.sample_one(origin[0] + x, origin[1] - z) - origin[2]

    if cfg.drone.tileset is not None:
        # The mesh may come from another flight than the terrain, and two flights do
        # not share a height until each is measured against the open model. Register
        # the mesh with its own elevation raster when the map names one.
        mesh_shift = height_shift
        if cfg.drone.mesh_elevation:
            mesh_shift = measure_vertical_shift(cfg.drone.mesh_elevation, dtm_paths, cfg.bbox)
            report["survey_mesh_height_shift_m"] = round(mesh_shift, 3)
        tiles = select_tiles(cfg.drone.tileset, cfg.drone.mesh_error_m)
        log(
            f"survey mesh, error {cfg.drone.mesh_error_m} m, {len(tiles)} tiles, "
            f"textures capped at {cfg.drone.mesh_texture_px} px, "
            f"height shift {mesh_shift:+.2f} m"
        )
        mesh_tiles = load_mesh_tiles(
            cfg.drone.tileset,
            cfg.drone.mesh_error_m,
            origin,
            height_shift=mesh_shift,
            max_px=cfg.drone.mesh_texture_px,
            quality=cfg.drone.mesh_jpeg_quality,
            bbox=cfg.bbox,
        )
        meshes.update(mesh_tiles)
        report["survey_mesh"] = {
            "max_error_m": cfg.drone.mesh_error_m,
            "tiles_selected": len(tiles),
            "meshes_in_box": len(mesh_tiles),
            "texture_px_cap": cfg.drone.mesh_texture_px,
            "jpeg_quality": cfg.drone.mesh_jpeg_quality,
        }
        report["sources"].append(
            {"dataset": "Own drone survey, 3D Tiles mesh", "files": [cfg.drone.tileset.name]}
        )

    if cfg.gates:
        log(f"course, {len(cfg.gates)} gates")
        clearance = check_clearance(cfg.gates, origin, ground_height, meshes)
        blocked = [c["gate"] for c in clearance if not c["clear"]]
        if blocked:
            log(f"[bold yellow]warning[/] gates not clear of the geometry: {blocked}")
        meshes.update(build_course(cfg.gates, origin, ground_height))
        report["course"] = {
            "gates": len(cfg.gates),
            "lap_length_m": round(course_length_m(cfg.gates), 1),
            "blocked_gates": blocked,
            "clearance": clearance,
        }

    if cfg.probes_enabled:
        log("probes")
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
    if cfg.private:
        # A map over a private site must not carry its address. The bounding box, the
        # origin and the names of the Maa-amet sheets each name the place to the
        # metre, and a report is the file most likely to be pasted somewhere public
        # next to a frame rate. The mesh itself has local coordinates only, so it
        # gives nothing away. Redact here rather than at the publish step: a rule that
        # a person has to remember is a rule that is broken once.
        for key in ("bbox_lest97", "origin_lest97", "origin_height_eh2000"):
            report.pop(key, None)
        for source in report["sources"]:
            source.pop("files", None)
        report["private"] = True
    (cfg.dist_dir / f"{cfg.name}-build-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    log(f"done: {size / 1e6:.1f} MB, {stats.triangles:,} triangles in {report['seconds']} s")
    return out
