"""A camera tour of a built map: still images and a smooth video, rendered offline.

The game has no free camera, no replay and no command line option that loads a map, so
an in-game tour always needs a person at the sticks. This module renders the same glTF
file that the game loads. It uses an offscreen OpenGL context, so it is deterministic
and it needs no game and no window. See ``docs/decisions.md``.

Axis order is the game order everywhere in this module: x east, y up, z south, meters.
A shot reads its target in L-EST97 (east, north) and converts it once, in ``load_tour``.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

SHOT_KINDS = ("orbit", "fly", "reveal")
SKY_ZENITH = (0.30, 0.48, 0.78)
SKY_HORIZON = (0.72, 0.80, 0.88)
SUN_AZIMUTH_DEG = 150.0
SUN_ELEVATION_DEG = 42.0


@dataclass(frozen=True)
class Shot:
    """One camera move. ``target``, ``start`` and ``end`` are game (x, z) in meters."""

    name: str
    kind: str
    seconds: float
    target: tuple[float, float]
    height_m: float = 90.0
    radius_m: float = 200.0
    turns: float = 0.35
    start_deg: float = 40.0
    look_height_m: float = 12.0
    # A "fly" shot with a look ahead distance looks at a point on its own path, that
    # many meters in front of the camera. Zero means that it looks at the end point.
    look_ahead_m: float = 0.0
    fov_deg: float = 45.0
    still_at: float = 0.5
    start: tuple[float, float] | None = None
    end: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        if self.kind not in SHOT_KINDS:
            raise ValueError(f"shot kind must be one of {list(SHOT_KINDS)}: {self.kind!r}")
        if self.seconds <= 0:
            raise ValueError(f"shot {self.name!r} needs seconds above 0")
        if self.kind == "fly" and (self.start is None or self.end is None):
            raise ValueError(f"shot {self.name!r} of kind 'fly' needs a start and an end")


@dataclass(frozen=True)
class Tour:
    """The tour of one map: the shots and the output format."""

    name: str
    shots: tuple[Shot, ...]
    fps: int = 60
    width: int = 1920
    height: int = 1080
    still_px: int = 1600
    jpeg_quality: int = 82
    # Zero means that the renderer computes the distance from the shot.
    fog_start_m: float = 0.0
    fog_end_m: float = 0.0

    @property
    def seconds(self) -> float:
        return sum(shot.seconds for shot in self.shots)

    def __post_init__(self) -> None:
        if self.width % 2 or self.height % 2:
            raise ValueError(f"the frame size must be even: {self.width} x {self.height}")

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)


def smoothstep(t: float | np.ndarray) -> float | np.ndarray:
    """Ease in and ease out. Maps 0 to 0 and 1 to 1, with zero slope at both ends."""
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class GroundHeights:
    """A height raster of the terrain, in game axes, for camera clearance.

    The terrain of a map is a regular grid, so the maximum vertex height in a cell of
    ``step`` meters is enough. Cells with no vertex keep the median height.
    """

    def __init__(self, vertices: np.ndarray, step: float = 4.0) -> None:
        pts = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
        if not len(pts):
            raise ValueError("the terrain has no vertices")
        self.step = float(step)
        self.xmin = float(pts[:, 0].min())
        self.zmin = float(pts[:, 2].min())
        columns = max(1, int(math.ceil((pts[:, 0].max() - self.xmin) / self.step)) + 1)
        rows = max(1, int(math.ceil((pts[:, 2].max() - self.zmin) / self.step)) + 1)
        grid = np.full((rows, columns), -np.inf, dtype=np.float32)
        cx = np.clip(np.rint((pts[:, 0] - self.xmin) / self.step).astype(np.int64), 0, columns - 1)
        cz = np.clip(np.rint((pts[:, 2] - self.zmin) / self.step).astype(np.int64), 0, rows - 1)
        np.maximum.at(grid, (cz, cx), pts[:, 1].astype(np.float32))
        # A cell with no vertex takes the median, so that a hole never pulls the camera down.
        grid[np.isneginf(grid)] = float(np.median(pts[:, 1]))
        self.grid = grid

    def sample(self, x: np.ndarray, z: np.ndarray) -> np.ndarray:
        """Terrain height at many game (x, z) points, in meters above the map origin."""
        rows, columns = self.grid.shape
        cx = np.clip(np.rint((np.asarray(x) - self.xmin) / self.step), 0, columns - 1)
        cz = np.clip(np.rint((np.asarray(z) - self.zmin) / self.step), 0, rows - 1)
        return self.grid[cz.astype(np.int64), cx.astype(np.int64)]

    def at(self, x: float, z: float) -> float:
        """Terrain height in meters above the map origin at game (x, z)."""
        return float(self.sample(np.array(x), np.array(z)))


@dataclass(frozen=True)
class Pose:
    """One camera frame: where the camera is, where it looks, and how wide it sees."""

    eye: tuple[float, float, float]
    look: tuple[float, float, float]
    fov_deg: float


def shot_poses(shot: Shot, ground: GroundHeights, fps: int) -> Iterator[Pose]:
    """Yield ``round(seconds * fps)`` poses of one shot, eased in and eased out."""
    count = max(1, int(round(shot.seconds * fps)))
    target_y = ground.at(*shot.target) + shot.look_height_m
    look = (shot.target[0], target_y, shot.target[1])
    for index in range(count):
        t = float(smoothstep(index / max(1, count - 1)))
        if shot.kind == "orbit":
            angle = math.radians(shot.start_deg + 360.0 * shot.turns * t)
            x = shot.target[0] + shot.radius_m * math.cos(angle)
            z = shot.target[1] + shot.radius_m * math.sin(angle)
            height = shot.height_m
        elif shot.kind == "reveal":
            angle = math.radians(shot.start_deg + 360.0 * shot.turns * t)
            radius = shot.radius_m * (0.25 + 0.75 * t)
            x = shot.target[0] + radius * math.cos(angle)
            z = shot.target[1] + radius * math.sin(angle)
            height = shot.height_m * (0.15 + 0.85 * t)
        else:
            assert shot.start is not None and shot.end is not None
            x = shot.start[0] + (shot.end[0] - shot.start[0]) * t
            z = shot.start[1] + (shot.end[1] - shot.start[1]) * t
            height = shot.height_m
            if shot.look_ahead_m > 0:
                length = math.hypot(shot.end[0] - shot.start[0], shot.end[1] - shot.start[1])
                ahead = min(1.0, t + shot.look_ahead_m / max(length, 1.0))
                ax = shot.start[0] + (shot.end[0] - shot.start[0]) * ahead
                az = shot.start[1] + (shot.end[1] - shot.start[1]) * ahead
                look = (ax, ground.at(ax, az) + shot.look_height_m, az)
        eye_y = ground.at(x, z) + height
        yield Pose((x, eye_y, z), look, shot.fov_deg)


def tour_poses(tour: Tour, ground: GroundHeights, fps: int | None = None) -> Iterator[Pose]:
    """Yield the poses of every shot, in order. The cut between two shots is hard."""
    for shot in tour.shots:
        yield from shot_poses(shot, ground, fps or tour.fps)


def still_index(tour: Tour, shot: Shot, fps: int | None = None) -> int:
    """The frame number of the still image of ``shot``, counted from the first frame."""
    rate = fps or tour.fps
    before = 0
    for other in tour.shots:
        count = max(1, int(round(other.seconds * rate)))
        if other is shot:
            return before + min(count - 1, int(round((count - 1) * other.still_at)))
        before += count
    raise ValueError(f"{shot.name!r} is not a shot of this tour")


def look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray | None = None) -> np.ndarray:
    """A 4x4 view matrix, right handed, for a camera at ``eye`` that looks at ``target``."""
    up = np.array([0.0, 1.0, 0.0]) if up is None else up
    forward = target - eye
    norm = np.linalg.norm(forward)
    forward = np.array([0.0, 0.0, -1.0]) if norm < 1e-9 else forward / norm
    if abs(float(np.dot(forward, up))) > 0.999:
        up = np.array([0.0, 0.0, -1.0])
    right = np.cross(forward, up)
    right = right / max(float(np.linalg.norm(right)), 1e-9)
    true_up = np.cross(right, forward)
    view = np.eye(4, dtype=np.float32)
    view[0, :3], view[1, :3], view[2, :3] = right, true_up, -forward
    view[:3, 3] = -view[:3, :3] @ eye
    return view


def perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    """A 4x4 projection matrix. ``fov_deg`` is the vertical field of view."""
    f = 1.0 / math.tan(math.radians(fov_deg) / 2.0)
    out = np.zeros((4, 4), dtype=np.float32)
    out[0, 0] = f / aspect
    out[1, 1] = f
    out[2, 2] = (far + near) / (near - far)
    out[2, 3] = (2.0 * far * near) / (near - far)
    out[3, 2] = -1.0
    return out


def sun_direction() -> tuple[float, float, float]:
    """The unit vector from the ground toward the sun, in game axes."""
    azimuth = math.radians(SUN_AZIMUTH_DEG)
    elevation = math.radians(SUN_ELEVATION_DEG)
    return (
        math.cos(elevation) * math.sin(azimuth),
        math.sin(elevation),
        math.cos(elevation) * math.cos(azimuth),
    )


def auto_tour(
    name: str,
    bounds: tuple[np.ndarray, np.ndarray],
    ground: GroundHeights,
    landmarks: list[tuple[float, float, float]] | None = None,
) -> Tour:
    """The tour of a map that declares no shots.

    It holds a wide orbit of the whole map, one orbit around each of the tallest
    structures, and a reveal at the spawn point. ``bounds`` is the (minimum, maximum)
    corner in game axes. ``landmarks`` are (x, z, height above the terrain) points.

    A map that names its landmarks in the TOML file gets a better tour. This one needs
    no configuration, so a new map has a tour on the day it is built.
    """
    low, high = np.asarray(bounds[0], float), np.asarray(bounds[1], float)
    center = ((low[0] + high[0]) / 2.0, (low[2] + high[2]) / 2.0)
    width = float(max(high[0] - low[0], high[2] - low[2]))
    shots = [
        Shot(
            name="overview",
            kind="orbit",
            seconds=14.0,
            target=center,
            radius_m=width * 0.62,
            height_m=width * 0.40,
            turns=0.30,
            look_height_m=width * 0.02,
            fov_deg=42.0,
        )
    ]
    for number, (x, z, height) in enumerate(landmarks or [], start=1):
        shots.append(
            Shot(
                name=f"landmark-{number}",
                kind="orbit",
                seconds=10.0,
                target=(x, z),
                radius_m=max(90.0, height * 2.5),
                height_m=max(60.0, height * 2.0),
                turns=0.30,
                start_deg=200.0 + 60.0 * number,
                look_height_m=height * 0.55,
            )
        )
    shots.append(
        Shot(
            name="spawn",
            kind="reveal",
            seconds=10.0,
            target=(0.0, 0.0),
            radius_m=min(260.0, width * 0.28),
            height_m=min(120.0, width * 0.14),
            turns=0.22,
            look_height_m=8.0,
        )
    )
    return Tour(name=name, shots=tuple(shots))


def _game_xz(
    raw: dict[str, Any], key: str, origin: tuple[float, float]
) -> tuple[float, float] | None:
    """Read a point of the TOML in L-EST97 or WGS84 and return game (x, z) in meters."""
    from fpv_maps.crs import wgs84_to_lest97

    if f"{key}_wgs84" in raw:
        east, north = wgs84_to_lest97(*raw[f"{key}_wgs84"])
    elif key in raw:
        east, north = float(raw[key][0]), float(raw[key][1])
    else:
        return None
    return (east - origin[0], -(north - origin[1]))


def load_tour(path: Path, name: str, origin: tuple[float, float]) -> Tour | None:
    """Read the ``[tour]`` section of a map TOML file, or return None if it has none.

    ``origin`` is the L-EST97 (east, north) origin of the map. Every point of a shot
    becomes game (x, z) here, so that the rest of the module needs no coordinate system.
    """
    import tomllib

    with Path(path).open("rb") as fh:
        raw = tomllib.load(fh)
    section = raw.get("tour")
    if section is None:
        return None

    shots: list[Shot] = []
    for index, item in enumerate(section.get("shot", []), start=1):
        target = _game_xz(item, "target", origin)
        start = _game_xz(item, "start", origin)
        end = _game_xz(item, "end", origin)
        if target is None:
            target = end if end is not None else (0.0, 0.0)
        fields = {
            key: float(item[key])
            for key in (
                "height_m",
                "radius_m",
                "turns",
                "start_deg",
                "look_height_m",
                "look_ahead_m",
                "fov_deg",
                "still_at",
            )
            if key in item
        }
        shots.append(
            Shot(
                name=str(item.get("name", f"shot-{index}")),
                kind=str(item.get("kind", "orbit")),
                seconds=float(item.get("seconds", 10.0)),
                target=target,
                start=start,
                end=end,
                **fields,
            )
        )
    if not shots:
        return None

    size = section.get("size", [1920, 1080])
    return Tour(
        name=name,
        shots=tuple(shots),
        fps=int(section.get("fps", 60)),
        width=int(size[0]),
        height=int(size[1]),
        still_px=int(section.get("still_px", 1600)),
        jpeg_quality=int(section.get("jpeg_quality", 82)),
        fog_start_m=float(section.get("fog_start_m", 0.0)),
        fog_end_m=float(section.get("fog_end_m", 0.0)),
    )
