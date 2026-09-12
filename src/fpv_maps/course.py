"""A fixed gate course, so that two maps can be flown on the same line.

The game has no free camera, no replay and no telemetry export, so a frame rate
number is only worth something when a person flies the same line twice. A course of
gates makes the line repeatable by eye: the pilot flies gate 1 to gate N in order and
reads the frame counter of the game.

The course is deliberately cheap. Every gate is four boxes, 48 triangles, one flat
color and no texture, so the course itself never moves the frame rate. Put the same
course in every variant of a map and the only difference left is the thing under test.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import trimesh

from fpv_maps.materials import color_material

#: Gate colors, in order. The course repeats them, so a pilot can call the next gate
#: by color. The first gate is white, which marks the start and the finish.
GATE_COLORS: tuple[tuple[int, int, int], ...] = (
    (245, 245, 245),
    (255, 90, 0),
    (0, 190, 255),
    (255, 220, 0),
    (0, 220, 90),
    (255, 0, 140),
)

GroundFn = Callable[[float, float], float]


@dataclass(frozen=True)
class Gate:
    """One gate of the course, placed in L-EST97 (east, north).

    ``height_m`` is the height of the gate center above the terrain. ``size_m`` is the
    inner side of the square. ``yaw_deg`` turns the gate about the vertical axis, 0
    meaning that a pilot flies through it heading north.
    """

    east: float
    north: float
    height_m: float = 6.0
    size_m: float = 5.0
    yaw_deg: float = 0.0
    bar_m: float = 0.25


def _bar(
    extents: tuple[float, float, float],
    center: tuple[float, float, float],
    yaw_deg: float,
    pivot: tuple[float, float, float],
) -> trimesh.Trimesh:
    """One box of a gate frame, turned about the vertical axis through ``pivot``."""
    box = trimesh.creation.box(extents=extents)
    box.apply_translation(center)
    angle = np.radians(yaw_deg)
    box.apply_transform(trimesh.transformations.rotation_matrix(angle, (0, 1, 0), pivot))
    return box


def _flat(mesh: trimesh.Trimesh, material) -> trimesh.Trimesh:
    """A flat color with planar UVs, so that the exporter writes a valid material."""
    v = mesh.vertices
    uv = np.column_stack([v[:, 0] + v[:, 2], v[:, 1]])
    mesh.visual = trimesh.visual.TextureVisuals(uv=uv, material=material)
    return mesh


def build_course(
    gates: tuple[Gate, ...],
    origin: tuple[float, float, float],
    ground: GroundFn,
) -> dict[str, trimesh.Trimesh]:
    """Gate meshes in game axes.

    ``ground(x, z)`` returns the terrain height in game axes, relative to the origin,
    so a gate stands the same height above the ground on every variant of a map.
    """
    out: dict[str, trimesh.Trimesh] = {}
    for index, gate in enumerate(gates, start=1):
        x = gate.east - origin[0]
        z = -(gate.north - origin[1])
        y = ground(x, z) + gate.height_m
        color = GATE_COLORS[(index - 1) % len(GATE_COLORS)]
        material = color_material(f"fpv_gate_{index:02d}", color)
        half = gate.size_m / 2 + gate.bar_m / 2
        bar, pivot = gate.bar_m, (x, y, z)
        parts = {
            "left": ((bar, gate.size_m + 2 * bar, bar), (x - half, y, z)),
            "right": ((bar, gate.size_m + 2 * bar, bar), (x + half, y, z)),
            "top": ((gate.size_m + 2 * bar, bar, bar), (x, y + half, z)),
            "bottom": ((gate.size_m + 2 * bar, bar, bar), (x, y - half, z)),
        }
        for part, (extents, center) in parts.items():
            out[f"course_gate{index:02d}_{part}"] = _flat(
                _bar(extents, center, gate.yaw_deg, pivot), material
            )
    return out


def check_clearance(
    gates: tuple[Gate, ...],
    origin: tuple[float, float, float],
    ground: GroundFn,
    obstacles: dict[str, trimesh.Trimesh],
    tube_m: float = 8.0,
) -> list[dict]:
    """Count the obstacle vertices inside every gate and on the line through it.

    A gate that a tree grows through is not a gate, and a course is only repeatable
    while every gate is flyable. The quality of a survey mesh changes from variant to
    variant, so a gate that is clear at 25 cm of error can be blocked at 3 cm. The
    build therefore measures this on every variant instead of trusting one check.

    ``obstacles`` is every mesh of the map except the course itself. The report gives,
    per gate, the vertices inside the opening and the vertices inside a tube of
    ``tube_m`` either side of it, which is the room a drone needs to line the gate up.
    """
    points = [
        np.asarray(mesh.vertices)
        for name, mesh in obstacles.items()
        if not name.startswith("course_")
    ]
    vertices = np.vstack(points) if points else np.empty((0, 3))
    out: list[dict] = []
    for index, gate in enumerate(gates, start=1):
        x = gate.east - origin[0]
        z = -(gate.north - origin[1])
        centre = np.array([x, ground(x, z) + gate.height_m, z])
        yaw = np.radians(gate.yaw_deg)
        through = np.array([np.sin(yaw), 0.0, -np.cos(yaw)])
        across = np.array([np.cos(yaw), 0.0, np.sin(yaw)])
        delta = vertices - centre
        along = delta @ through
        side = delta @ across
        up = delta[:, 1]
        half = gate.size_m / 2
        in_gate = (np.abs(along) < 1.5) & (np.abs(side) < half) & (np.abs(up) < half)
        in_tube = (np.abs(along) < tube_m) & (np.abs(side) < half * 0.6) & (np.abs(up) < half * 0.6)
        out.append(
            {
                "gate": index,
                "in_opening": int(in_gate.sum()),
                "in_approach": int(in_tube.sum()),
                "clear": bool(in_gate.sum() == 0 and in_tube.sum() == 0),
            }
        )
    return out


def course_length_m(gates: tuple[Gate, ...]) -> float:
    """The length of the line that visits every gate in order and returns to the first."""
    if len(gates) < 2:
        return 0.0
    points = np.array([(g.east, g.north) for g in (*gates, gates[0])])
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())
