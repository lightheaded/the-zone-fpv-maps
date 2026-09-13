"""Fotoladu oblique photo metadata and camera resection.

The Maa-amet oblique photo service publishes, for one ground point, the photos that
see it. Each record gives the four ground corners of the frame, the flight height and
the image size, and no camera position, angles or focal length. This module recovers
those by a resection on the four corners.

Metadata comes from the documented API, see docs/analysis.md section 4:
    https://fotoladu.maaamet.ee/api.php?x=<east>&y=<north>   (L-EST97)
"""

from __future__ import annotations

import math
import re
import urllib.request
from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares

from fpv_maps import __version__
from fpv_maps.crs import wgs84_to_lest97

API = "https://fotoladu.maaamet.ee/api.php"
UA = f"the-zone-fpv-maps/{__version__} (map pipeline; contact via GitHub lightheaded)"

# Sensor width in mm by the camera folder name that the tile path carries.
SENSOR_MM = {"a7r": 35.9, "a7r2": 35.9, "a7r3": 35.9, "a7r4": 35.7, "nex7": 23.5}

_RECORD = re.compile(
    r"pilt\('(?P<id>\d+)','(?P<image>[^']+)','(?P<tiled>\d)','(?P<rada>[^']+)',"
    r"'(?P<w>\d+)',(?P<h>\d+),[-\d.]+,[-\d.]+,(?P<corners>(?:[-\d.]+,){8})"
    r"(?P<korgus>\d+),[^,]+,(?P<tapsus>\d+),(?P<date>[\d-]+),(?P<tyyp>\d+)\)"
)


@dataclass(frozen=True)
class Photo:
    """One oblique photo, as the service describes it."""

    id: str
    image: str
    rada: str
    width: int
    height: int
    corners: tuple[tuple[float, float], ...]  # L-EST97 (east, north), 4 of them
    korgus_m: float
    date: str
    accuracy: int
    tiled: bool

    @property
    def camera(self) -> str:
        return self.rada.split("/")[1]

    @property
    def sensor_mm(self) -> float:
        return SENSOR_MM.get(self.camera, 35.9)

    @property
    def centre(self) -> tuple[float, float]:
        return (
            sum(c[0] for c in self.corners) / 4.0,
            sum(c[1] for c in self.corners) / 4.0,
        )

    def tile_url(self, level: int, col: int, row: int) -> str:
        return f"https://fotoladu.maaamet.ee/read_tiles.php?{self.image}/{level}/{col}_{row}.jpg"


def query(east: float, north: float, timeout: float = 60.0) -> list[Photo]:
    """Every photo that sees the L-EST97 point, newest first."""
    url = f"{API}?x={north:.0f}&y={east:.0f}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        html = fh.read().decode("utf-8", "replace")
    out: list[Photo] = []
    for m in _RECORD.finditer(html):
        v = [float(s) for s in m.group("corners").rstrip(",").split(",")]
        corners = tuple(wgs84_to_lest97(v[i + 1], v[i]) for i in (0, 2, 4, 6))
        out.append(
            Photo(
                id=m.group("id"),
                image=m.group("image"),
                rada=m.group("rada"),
                width=int(m.group("w")),
                height=int(m.group("h")),
                corners=corners,
                korgus_m=float(m.group("korgus")),
                date=m.group("date"),
                accuracy=int(m.group("tapsus")),
                tiled=m.group("tiled") == "1",
            )
        )
    out.sort(key=lambda p: p.date, reverse=True)
    return out


@dataclass(frozen=True)
class Camera:
    """A resected frame camera. World is L-EST97 (east, north, up) in meters."""

    f_px: float
    centre: np.ndarray  # (3,) east, north, up
    rotation: np.ndarray  # (3, 3) world -> camera, rows are the camera axes
    width: int
    height: int
    rms_px: float
    tilt_deg: float
    ground_z: float

    @property
    def focal_mm_of(self) -> float:
        return self.f_px

    def project(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """World points (N, 3) to pixel (N, 2) and depth (N,). Origin is the image centre."""
        w = points - self.centre
        cam = w @ self.rotation.T
        depth = cam[:, 2]
        safe = np.where(np.abs(depth) < 1e-6, 1e-6, depth)
        uv = np.column_stack([self.f_px * cam[:, 0] / safe, self.f_px * cam[:, 1] / safe])
        return uv, depth


def _axes(az: float, tilt: float, roll: float) -> np.ndarray:
    d = np.array([math.sin(tilt) * math.sin(az), math.sin(tilt) * math.cos(az), -math.cos(tilt)])
    up = np.array([0.0, 0.0, 1.0])
    x = np.cross(d, up)
    n = np.linalg.norm(x)
    x = x / n if n > 1e-9 else np.array([1.0, 0.0, 0.0])
    y = np.cross(d, x)
    cr, sr = math.cos(roll), math.sin(roll)
    return np.array([x * cr + y * sr, -x * sr + y * cr, d])


def _vanishing_azimuth(corners: np.ndarray) -> list[float]:
    """Seed azimuths from the edge pair that converges. Returns 0, 1 or 2 candidates."""
    out = []
    c = corners.mean(axis=0)
    for a, b, p, q in ((0, 1, 3, 2), (1, 2, 0, 3)):
        l1 = np.cross(np.array([*corners[a], 1.0]), np.array([*corners[b], 1.0]))
        l2 = np.cross(np.array([*corners[p], 1.0]), np.array([*corners[q], 1.0]))
        v = np.cross(l1, l2)
        if abs(v[2]) < 1e-12:
            continue
        vp = np.array([v[0] / v[2], v[1] / v[2]])
        d = np.linalg.norm(vp - c)
        if d > 20000.0:  # effectively parallel, carries no tilt direction
            continue
        to = c - vp
        out.append(math.atan2(to[0], to[1]))
    return out


def resect_candidates(
    photo: Photo,
    ground_z: float | np.ndarray = 0.0,
    orderings: list[tuple[int, bool]] | None = None,
) -> list[Camera]:
    """Every plausible camera that fits the four ground corners.

    The API gives the corners as a ring, but not which corner of the frame each one is.
    So the fit tries all eight ways to map the ring onto the frame. Several of them fit
    to a pixel or better, and they are different cameras: the frame turned by a quarter
    or a half turn, or mirrored. The corner residual cannot tell them apart, because
    four coplanar points barely determine a camera at all. Measured on Tartu, the lowest
    residual is the right pose about half the time, and a fit with a residual of 0.5 px
    on a 7952 px frame can still point somewhere else entirely.

    So this returns all of them and lets the caller decide. Score them against the
    orthophoto, which is independent evidence: see ``orthocheck.score``.

    ``ground_z`` is the height of each corner. Pass the terrain height per corner, not
    one plane: the corners lie up to a kilometre apart, and a plane through the wrong
    height moves the camera up or down by the same error. A 6 m error moves a facade
    by about 60 pixels in the frame, which is more than the facade is tall.
    """
    zs = np.broadcast_to(np.asarray(ground_z, dtype=float), (4,))
    ground = np.array([[e, n, z] for (e, n), z in zip(photo.corners, zs, strict=True)], dtype=float)
    ground_z = float(zs.mean())
    c2 = ground[:, :2]
    w, h = photo.width, photo.height
    base = [(-w / 2, -h / 2), (-w / 2, h / 2), (w / 2, h / 2), (w / 2, -h / 2)]
    seeds = _vanishing_azimuth(c2)
    if not seeds:
        seeds = list(np.linspace(0, 2 * math.pi, 8, endpoint=False))
    else:
        seeds = [a + d for a in seeds for d in (0.0, math.pi)]
    centre = c2.mean(axis=0)
    out: list[Camera] = []
    seen: set[tuple] = set()
    if orderings is None:
        orderings = [(rot, rev) for rot in range(4) for rev in (False, True)]
    for rot, rev in orderings:
        if True:
            idx = list(range(4))[rot:] + list(range(4))[:rot]
            if rev:
                idx = idx[::-1]
            img = np.array([base[i] for i in idx], dtype=float)

            def residual(p: np.ndarray, img: np.ndarray = img) -> np.ndarray:
                f, x, y, z, az, tilt, roll = p
                rot_m = _axes(az, tilt, roll)
                w0 = ground - np.array([x, y, z])
                cam = w0 @ rot_m.T
                dz = np.where(cam[:, 2] > 1.0, cam[:, 2], 1.0)
                return np.concatenate(
                    [f * cam[:, 0] / dz - img[:, 0], f * cam[:, 1] / dz - img[:, 1]]
                )

            for az0 in seeds:
                for roll0 in (0.0, math.pi):
                    p0 = np.array(
                        [
                            13000.0,
                            centre[0],
                            centre[1],
                            ground_z + photo.korgus_m,
                            az0,
                            0.78,
                            roll0,
                        ]
                    )
                    sol = least_squares(residual, p0, max_nfev=3000)
                    rms = math.sqrt(2.0 * sol.cost / 8.0)
                    f, ex, ny, z, az, tilt, roll = sol.x
                    tilt_deg = math.degrees(tilt) % 360.0
                    if tilt_deg > 180.0:
                        tilt_deg = 360.0 - tilt_deg
                    height = z - ground_z
                    # korgus is above sea level and the fit is above the ground plane,
                    # so the fit must be lower, but not by more than the city relief.
                    if not (0.4 * photo.korgus_m < height < 1.05 * photo.korgus_m):
                        continue
                    if not (5.0 < tilt_deg < 75.0):
                        continue
                    if rms > 0.01 * photo.width:
                        continue
                    key = (round(ex / 5.0), round(ny / 5.0), round(z / 5.0), round(abs(f) / 50.0))
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(_camera(photo, sol.x, rms, ground_z))
    return out


def _camera(photo: Photo, x: np.ndarray, rms: float, ground_z: float) -> Camera:
    f, ex, ny, z, az, tilt, roll = x
    tilt_deg = math.degrees(tilt) % 360.0
    if tilt_deg > 180.0:
        tilt_deg = 360.0 - tilt_deg
    return Camera(
        f_px=abs(f),
        centre=np.array([ex, ny, z]),
        rotation=_axes(az, tilt, roll),
        width=photo.width,
        height=photo.height,
        rms_px=rms,
        tilt_deg=tilt_deg,
        ground_z=ground_z,
    )


def resect(photo: Photo, ground_z: float | np.ndarray = 0.0) -> Camera | None:
    """The candidate with the lowest corner residual, or ``None``.

    Kept for callers that have no independent evidence to choose with. Read the warning
    on ``resect_candidates``: this picks the right pose only about half the time.
    """
    cands = resect_candidates(photo, ground_z)
    return min(cands, key=lambda c: c.rms_px) if cands else None
