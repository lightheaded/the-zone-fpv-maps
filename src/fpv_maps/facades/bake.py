"""Bake facade textures onto LOD2 walls from resected Fotoladu oblique photos."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import trimesh

from fpv_maps.facades.fotoladu import Camera, Photo
from fpv_maps.facades.walls import Panel

COARSE_M = 1.5  # occlusion is tested on this grid, colour on the texel grid
MIN_INCIDENCE = 0.35  # cos of the angle between wall normal and the view ray
BLEND_POWER = 4.0  # how hard the best source outweighs the next one
MIN_BLEND_WEIGHT = 0.02  # a source worth less than this adds noise, not detail


@dataclass
class Source:
    photo: Photo
    camera: Camera
    image: np.ndarray  # (H, W, 3) uint8 at this level
    scale: float  # level pixels per full-frame pixel
    offset: tuple[int, int]  # (x, y) of image[0,0] inside the level


def _sample(src: Source, uv: np.ndarray) -> np.ndarray:
    """Bilinear sample. ``uv`` is full-frame pixels with the origin at the centre."""
    h, w = src.image.shape[:2]
    x = (uv[:, 0] + src.camera.width / 2.0) * src.scale - src.offset[0]
    y = (uv[:, 1] + src.camera.height / 2.0) * src.scale - src.offset[1]
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx = (x - x0)[:, None]
    fy = (y - y0)[:, None]
    x0c = np.clip(x0, 0, w - 2)
    y0c = np.clip(y0, 0, h - 2)
    im = src.image
    c = (
        im[y0c, x0c] * (1 - fx) * (1 - fy)
        + im[y0c, x0c + 1] * fx * (1 - fy)
        + im[y0c + 1, x0c] * (1 - fx) * fy
        + im[y0c + 1, x0c + 1] * fx * fy
    )
    inside = (x >= 0) & (x < w - 1) & (y >= 0) & (y < h - 1)
    return c, inside


def _grid(panel: Panel, step: float) -> tuple[np.ndarray, int, int]:
    nu = max(1, int(math.ceil(panel.width / step)))
    nv = max(1, int(math.ceil(panel.height / step)))
    us = (np.arange(nu) + 0.5) * (panel.width / nu)
    vs = (np.arange(nv) + 0.5) * (panel.height / nv)
    uu, vv = np.meshgrid(us, vs)
    pts = panel.origin + uu.reshape(-1, 1) * panel.u_axis + vv.reshape(-1, 1) * panel.v_axis
    return pts, nu, nv


def pack(panels: list[Panel], texel_m: float, max_px: int = 8192) -> tuple[int, int]:
    """Shelf pack the panels into an atlas. Sets ``uv0`` and ``px`` on each panel."""
    order = sorted(range(len(panels)), key=lambda i: -panels[i].height)
    x = y = shelf = 0
    for i in order:
        p = panels[i]
        w = max(2, int(math.ceil(p.width / texel_m)) + 2)
        h = max(2, int(math.ceil(p.height / texel_m)) + 2)
        w = min(w, max_px)
        h = min(h, max_px)
        if x + w > max_px:
            x = 0
            y += shelf
            shelf = 0
        p.uv0 = (x, y)
        p.px = (w, h)
        x += w
        shelf = max(shelf, h)
    return max_px, y + shelf


def _nearest(panel: Panel, donor_panels: np.ndarray, donor_at: np.ndarray) -> int | None:
    """The covered panel closest to this one, or ``None`` when nothing is covered."""
    if not len(donor_panels):
        return None
    d = donor_at - panel.origin
    return int(donor_panels[int(np.argmin(np.einsum("ij,ij->i", d, d)))])


def bake(
    panels: list[Panel],
    sources: list[Source],
    occluder: trimesh.Trimesh,
    texel_m: float,
    atlas_px: tuple[int, int],
    log=print,
) -> tuple[np.ndarray, np.ndarray]:
    """Fill the atlas. Returns the RGB atlas and a per-panel count of filled texels."""
    width, height = atlas_px
    atlas = np.zeros((height, width, 3), dtype=np.uint8)
    covered = np.zeros(len(panels), dtype=np.float32)
    empty: list[int] = []
    totals: list[np.ndarray] = []
    n_filled = 0

    # 1. Coarse visibility, one big ray batch per source.
    log(f"visibility: {len(panels)} panels x {len(sources)} photos")
    coarse: list[tuple[np.ndarray, int, int]] = [_grid(p, COARSE_M) for p in panels]
    counts = np.array([c[0].shape[0] for c in coarse])
    starts = np.concatenate([[0], np.cumsum(counts)])
    allpts = np.concatenate([c[0] for c in coarse])
    normals = np.concatenate(
        [
            np.repeat(p.normal[None, :], c[0].shape[0], axis=0)
            for p, c in zip(panels, coarse, strict=True)
        ]
    )
    vis = np.zeros((len(sources), allpts.shape[0]), dtype=bool)
    for si, s in enumerate(sources):
        eye = s.camera.centre
        d = eye - allpts
        dist = np.linalg.norm(d, axis=1)
        dirn = d / dist[:, None]
        inc = np.einsum("ij,ij->i", normals, dirn)
        cand = inc > MIN_INCIDENCE
        uv, depth = s.camera.project(allpts)
        cand &= depth > 0
        cand &= np.abs(uv[:, 0]) < s.camera.width / 2 - 2
        cand &= np.abs(uv[:, 1]) < s.camera.height / 2 - 2
        idx = np.flatnonzero(cand)
        ok = np.zeros(allpts.shape[0], dtype=bool)
        if len(idx):
            org = allpts[idx] + normals[idx] * 0.25
            hit = occluder.ray.intersects_first(ray_origins=org, ray_directions=dirn[idx])
            ok[idx] = hit < 0  # -1 means the ray escaped: nothing between wall and camera
        vis[si] = ok
        log(f"  {s.photo.date} {s.photo.image[-6:]}  visible coarse points {ok.sum():,}")

    # 2. Weigh the sources per panel, then blend every one that sees a texel.
    log("sampling")
    for pi, p in enumerate(panels):
        n0, n1 = starts[pi], starts[pi + 1]
        nu, nv = coarse[pi][1], coarse[pi][2]
        score = []
        for si, s in enumerate(sources):
            v = vis[si, n0:n1]
            if not v.any():
                continue
            d = s.camera.centre - p.origin
            dist = float(np.linalg.norm(d))
            inc = float(np.dot(p.normal, d / dist))
            score.append((v.mean() * inc / max(dist, 1.0), si))
        if not score:
            empty.append(pi)
            continue
        score.sort(reverse=True)
        pw, ph = p.px
        us = (np.arange(pw) + 0.5) * (p.width / pw)
        vs = (np.arange(ph) + 0.5) * (p.height / ph)
        uu, vv = np.meshgrid(us, vs)
        pts = p.origin + uu.reshape(-1, 1) * p.u_axis + vv.reshape(-1, 1) * p.v_axis
        # map each texel to its coarse cell
        ci = np.clip((uu.reshape(-1) / p.width * nu).astype(int), 0, nu - 1)
        cj = np.clip((vv.reshape(-1) / p.height * nv).astype(int), 0, nv - 1)
        cell = cj * nu + ci
        # Every source that sees a texel contributes to it, weighted by how well it
        # sees it. Taking only the best one leaves a hard seam wherever the best
        # source changes, inside a panel and between two panels of the same wall, and
        # a facade cut into mismatched strips is what reads as a broken texture. The
        # weight is raised to a power so that the best source still dominates and the
        # others fill its gaps and soften the join, rather than averaging a wall into
        # mush. The poses agree to a few decimetres, which is about one texel here.
        acc = np.zeros((pts.shape[0], 3), dtype=np.float32)
        weight = np.zeros(pts.shape[0], dtype=np.float32)
        top = score[0][0]
        for rank, si in score:
            w = float((rank / top) ** BLEND_POWER)
            if w < MIN_BLEND_WEIGHT:
                break
            v = vis[si, n0:n1]
            take = v[cell]
            if not take.any():
                continue
            s = sources[si]
            uv, depth = s.camera.project(pts[take])
            col, inside = _sample(s, uv)
            good = inside & (depth[: len(inside)] > 0)
            sel = np.flatnonzero(take)[good]
            acc[sel] += col[good] * w
            weight[sel] += w
        filled = weight > 0
        if not filled.any():
            empty.append(pi)
            continue
        out = np.zeros((pts.shape[0], 3), dtype=np.float32)
        out[filled] = acc[filled] / weight[filled, None]
        # fill the gaps with the panel's own mean, so no black holes remain
        mean = out[filled].mean(axis=0)
        out[~filled] = mean
        totals.append(out[filled].sum(axis=0))
        n_filled += int(filled.sum())
        covered[pi] = filled.mean()
        x0, y0 = p.uv0
        tile = out.reshape(ph, pw, 3)[::-1]  # v grows up, atlas rows grow down
        atlas[y0 : y0 + ph, x0 : x0 + pw] = np.clip(tile, 0, 255).astype(np.uint8)

    # A panel no photo could see keeps its patch of the atlas, and an untouched patch
    # is black. Black reads as a hole in the wall, which is worse than a plain wall: it
    # is the one thing that looks like a fault rather than like missing detail.
    #
    # A flat colour is not much better. Half of the wall area of an old town is a
    # courtyard or a party wall that no aerial photo can see, so a flat fill is what a
    # pilot in a narrow street looks at most of the time, and it reads as an untextured
    # map. So a panel with no photo borrows from the best covered wall of its own
    # building instead. Both patches use the same texel size, so the borrowed picture
    # is tiled, never stretched: a window stays the size of a window. The result is not
    # the true wall, and it is the same house, the same age and the same material.
    if n_filled and empty:
        avg = np.clip(np.sum(totals, axis=0) / n_filled, 0, 255).astype(np.uint8)
        donors: dict[str, int] = {}
        for pi, panel in enumerate(panels):
            if covered[pi] <= 0.0:
                continue
            best = donors.get(panel.building)
            if best is None or panels[best].area * covered[best] < panel.area * covered[pi]:
                donors[panel.building] = pi
        # A building where no wall at all got a photo borrows from the nearest building
        # that did. Neighbours in a street are the same age and the same material far
        # more often than not, so this is a much closer guess than the city average,
        # and it leaves almost no flat wall anywhere.
        donor_panels = np.array(sorted(donors.values()))
        donor_at = (
            np.array([panels[i].origin for i in donor_panels])
            if len(donor_panels)
            else np.zeros((0, 3))
        )
        borrowed = 0
        for pi in empty:
            panel = panels[pi]
            x0, y0 = panel.uv0
            pw, ph = panel.px
            donor = donors.get(panel.building)
            if donor is None:
                donor = _nearest(panel, donor_panels, donor_at)
            if donor is None:
                atlas[y0 : y0 + ph, x0 : x0 + pw] = avg
                continue
            dp = panels[donor]
            dx, dy = dp.uv0
            dw, dh = dp.px
            src = atlas[dy : dy + dh, dx : dx + dw]
            tile = np.tile(src, (ph // dh + 1, pw // dw + 1, 1))
            # Align the bottom, not the top. Atlas row 0 is the top of a wall, and the
            # two walls are rarely the same height. Tiling from the top puts the
            # donor's roofline half way up the target and its ground floor in the air.
            # Taking the last rows keeps a door at the door and a shop front on the
            # street, which is the part of a wall a drone at 3 m actually flies past.
            atlas[y0 : y0 + ph, x0 : x0 + pw] = tile[-ph:, :pw]
            borrowed += 1
        log(
            f"panels with no photo at all: {len(empty)} of {len(panels)}. "
            f"{borrowed} borrowed a wall of their own building, "
            f"{len(empty) - borrowed} took the average facade colour"
        )
    return atlas, covered
