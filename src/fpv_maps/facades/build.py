"""Buildings whose walls carry a photo of themselves.

The LOD2 building model of Maa- ja Ruumiamet has the shape of every house and nothing
of its surface, so a whole city reads as one concrete texture. The oblique photo
service of the same agency has pictures of those walls, taken from four directions.
This module puts the second on the first.

The chain is: group the wall triangles into flat panels, choose the photos and fit a
camera to each, pack the panels into one atlas, and fill each texel from the best
photo that can see it and is not blocked by another building.

Roofs take the orthophoto instead. It is 10 cm data that already sees every roof from
straight above, it needs no oblique photo and no fit, and it is what a map reads like
from the air.

**The photos are not licensed for redistribution.** A map built by this module stays
on the machine that built it. See `docs/licensing.md`.
"""

from __future__ import annotations

import numpy as np
import trimesh

from fpv_maps.buildings import BuildingSet, _face_normals
from fpv_maps.crs import BBox, to_game
from fpv_maps.facades import bake, sources
from fpv_maps.facades.orthocheck import ground_control
from fpv_maps.facades.walls import wall_panels
from fpv_maps.materials import jpeg_image, texture_material
from fpv_maps.terrain import HeightField

#: A face whose normal points up by more than this is a roof, not a wall.
ROOF_NORMAL_Z = 0.35


def _occluder(buildings: BuildingSet) -> trimesh.Trimesh:
    """Every building as one mesh, for the visibility rays.

    A wall is only textured from a photo that has a clear line to it. Without this,
    the far side of a block takes the picture of the near side, which paints a street
    onto a courtyard wall.
    """
    tris = np.concatenate([b.vertices[b.faces] for b in buildings.buildings])
    verts = tris.reshape(-1, 3)
    return trimesh.Trimesh(
        vertices=verts, faces=np.arange(len(verts)).reshape(-1, 3), process=False
    )


def _wall_mesh(panels, atlas_px, origin, material) -> trimesh.Trimesh:
    """The wall triangles with atlas texture coordinates."""
    width, height = atlas_px
    tris, uvs = [], []
    for p in panels:
        x0, y0 = p.uv0
        pw, ph = p.px
        for tri in p.tris:
            local = p.to_uv(tri)
            u = (x0 + pw * (local[:, 0] / max(p.width, 1e-6))) / width
            v = (y0 + ph * (1.0 - local[:, 1] / max(p.height, 1e-6))) / height
            tris.append(tri)
            uvs.append(np.column_stack([u, v]))
    verts = to_game(np.array(tris).reshape(-1, 3), origin)
    mesh = trimesh.Trimesh(
        vertices=verts, faces=np.arange(len(verts)).reshape(-1, 3), process=False
    )
    mesh.visual = trimesh.visual.TextureVisuals(uv=np.concatenate(uvs), material=material)
    return mesh


def _roof_mesh(buildings: BuildingSet, bbox: BBox, origin, material) -> trimesh.Trimesh:
    """The roof triangles, with the orthophoto mapped onto them from above.

    Game axes are x east and z south, so the north edge of the box is V = 0, the same
    convention the terrain uses.
    """
    tris = []
    for b in buildings.buildings:
        faces = b.vertices[b.faces]
        normals = _face_normals(b.vertices, b.faces)
        roof = faces[normals[:, 2] > ROOF_NORMAL_Z]
        if len(roof):
            tris.append(roof)
    verts = to_game(np.concatenate(tris).reshape(-1, 3), origin)
    mesh = trimesh.Trimesh(
        vertices=verts, faces=np.arange(len(verts)).reshape(-1, 3), process=False
    )
    u = (verts[:, 0] + origin[0] - bbox.xmin) / bbox.width
    v = (bbox.ymax - (origin[1] - verts[:, 2])) / bbox.height
    mesh.visual = trimesh.visual.TextureVisuals(uv=np.column_stack([u, v]), material=material)
    return mesh


def build_facade_buildings(
    buildings: BuildingSet,
    cfg,
    origin: tuple[float, float, float],
    field: HeightField,
    corner_field: HeightField,
    ortho_rgb: np.ndarray,
    ground_material,
    log=print,
) -> tuple[dict[str, trimesh.Trimesh], dict]:
    """Wall and roof meshes with photo textures, and a report of what the bake reached.

    ``field`` is the terrain over the map box and ``corner_field`` reaches far enough
    outside it to hold the corners of a whole photo frame.
    """
    facades = cfg.facades
    cache_dir = cfg.data_dir / "fotoladu"
    report: dict = {
        "deep_zoom_level": facades.level,
        "texel_m": facades.texel_m,
        "atlas_px": facades.atlas_px,
    }

    gc_pts, gc_lum = ground_control(cfg.bbox, ortho_rgb, buildings, field)
    log(f"ground control points on open ground: {len(gc_pts)}")

    def choose():
        return sources.select(
            cfg.bbox,
            cfg.origin,
            origin[2],
            corner_field,
            gc_pts,
            gc_lum,
            cache_dir,
            facades.max_candidates,
            facades.max_sources,
            facades.min_correlation,
            log=log,
        )

    chosen = sources.load(cache_dir / f"sources-{cfg.name}.json", choose, log=log)
    if not chosen:
        raise RuntimeError(
            "no oblique photo of this box has a pose that the orthophoto agrees with"
        )
    frames = sources.frames(chosen, cache_dir, facades.level)
    report["photos"] = [
        {"image": p.image, "date": p.date, "correlation": round(corr, 3)} for p, _c, corr in chosen
    ]

    panels = wall_panels(buildings)
    atlas_px = bake.pack(panels, facades.texel_m, max_px=facades.atlas_px)
    log(f"wall panels {len(panels)}, atlas {atlas_px[0]} x {atlas_px[1]} px")
    atlas, covered = bake.bake(
        panels, frames, _occluder(buildings), facades.texel_m, atlas_px, log=log
    )
    area = np.array([p.area for p in panels])
    weighted = float((covered * area).sum() / area.sum())
    log(f"wall coverage: {weighted * 100:.1f}% of the wall area carries a photo")
    report.update(
        {
            "panels": len(panels),
            "atlas_px": list(atlas_px),
            "panels_with_photo": int((covered > 0).sum()),
            "area_weighted_coverage": round(weighted, 4),
        }
    )

    wall_material = texture_material("fpv_facades", jpeg_image(atlas, facades.jpeg_quality))
    return (
        {
            "buildings_walls": _wall_mesh(panels, atlas_px, origin, wall_material),
            "buildings_roofs": _roof_mesh(buildings, cfg.bbox, origin, ground_material),
        },
        report,
    )


__all__ = ["build_facade_buildings"]
