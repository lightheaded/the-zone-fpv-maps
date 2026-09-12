"""Group LOD2 wall triangles into flat wall panels with a local 2D frame."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh

from fpv_maps.buildings import BuildingSet


@dataclass
class Panel:  # noqa: D101
    """One flat wall of one building, in L-EST97 (east, north, up)."""

    building: str
    normal: np.ndarray  # (3,) unit, points out of the wall
    origin: np.ndarray  # (3,) world point of the panel's (u=0, v=0) corner
    u_axis: np.ndarray  # (3,) unit, horizontal along the wall
    v_axis: np.ndarray  # (3,) unit, up
    width: float
    height: float
    tris: np.ndarray  # (n, 3, 3) world triangles that belong to the panel
    uv0: tuple[int, int] = (0, 0)  # atlas pixel of the panel origin
    px: tuple[int, int] = (0, 0)  # atlas pixel size

    @property
    def area(self) -> float:
        return self.width * self.height

    def to_uv(self, pts: np.ndarray) -> np.ndarray:
        d = pts - self.origin
        return np.column_stack([d @ self.u_axis, d @ self.v_axis])


def wall_panels(
    buildings: BuildingSet, max_tilt: float = 0.35, min_area: float = 6.0
) -> list[Panel]:
    """Every near vertical face of every building, grouped by its plane.

    ``max_tilt`` is the largest |normal.z| that still counts as a wall.
    """
    panels: list[Panel] = []
    up = np.array([0.0, 0.0, 1.0])
    for b in buildings.buildings:
        first = len(panels)
        v = b.vertices
        tri = v[b.faces]  # (F, 3, 3)
        e1 = tri[:, 1] - tri[:, 0]
        e2 = tri[:, 2] - tri[:, 0]
        n = np.cross(e1, e2)
        ln = np.linalg.norm(n, axis=1)
        keep = ln > 1e-9
        if not keep.any():
            continue
        n = n[keep] / ln[keep, None]
        tri = tri[keep]
        wall = np.abs(n[:, 2]) < max_tilt
        if not wall.any():
            continue
        n, tri = n[wall], tri[wall]
        # horizontal normal, quantised so coplanar faces land in one bucket
        h = n.copy()
        h[:, 2] = 0.0
        hl = np.linalg.norm(h, axis=1)
        good = hl > 1e-9
        n, tri, h, hl = n[good], tri[good], h[good], hl[good]
        if len(tri) == 0:
            continue
        h = h / hl[:, None]
        offset = np.einsum("ij,ij->i", h, tri[:, 0])
        key = np.column_stack(
            [np.round(np.arctan2(h[:, 1], h[:, 0]) / 0.09), np.round(offset / 0.6)]
        )
        seen: dict[tuple[float, float], list[int]] = {}
        for i, k in enumerate(map(tuple, key)):
            seen.setdefault(k, []).append(i)
        for idx in seen.values():
            sel = np.array(idx)
            nn = h[sel].mean(axis=0)
            nl = np.linalg.norm(nn)
            if nl < 1e-9:
                continue
            nn = nn / nl
            u = np.cross(up, nn)
            ul = np.linalg.norm(u)
            if ul < 1e-9:
                continue
            u = u / ul
            pts = tri[sel].reshape(-1, 3)
            uu = pts @ u
            vv = pts @ up
            w = float(uu.max() - uu.min())
            hgt = float(vv.max() - vv.min())
            if w * hgt < min_area or w < 1.0 or hgt < 1.0:
                continue
            base = pts[0] - (uu[0] - uu.min()) * u - (vv[0] - vv.min()) * up
            panels.append(
                Panel(
                    building=b.name,
                    normal=nn,
                    origin=base,
                    u_axis=u,
                    v_axis=up.copy(),
                    width=w,
                    height=hgt,
                    tris=tri[sel],
                )
            )
        _orient_outward(panels, first, b)
    return panels


def _orient_outward(panels: list[Panel], first: int, building) -> None:
    """Flip any panel whose normal points into its own building.

    The Maa-amet OBJ does not wind every face the same way. About one wall in six
    faced inward, and a wall with an inward normal takes its texture from a camera on
    the far side of the building, which paints the street behind it onto the wall.
    """
    if first >= len(panels):
        return
    mesh = trimesh.Trimesh(vertices=building.vertices, faces=building.faces, process=False)
    if not mesh.is_watertight:
        return
    probe = np.array(
        [
            p.origin + p.u_axis * p.width / 2 + p.v_axis * p.height / 2 + p.normal * 0.30
            for p in panels[first:]
        ]
    )
    try:
        inside = mesh.contains(probe)
    except Exception:
        return
    for p, bad in zip(panels[first:], inside, strict=True):
        if bad:
            p.normal = -p.normal
            p.u_axis = -p.u_axis
            pts = p.tris.reshape(-1, 3)
            uu = pts @ p.u_axis
            vv = pts @ p.v_axis
            p.origin = pts[0] - (uu[0] - uu.min()) * p.u_axis - (vv[0] - vv.min()) * p.v_axis
