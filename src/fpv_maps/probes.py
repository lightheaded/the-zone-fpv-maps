"""Test objects near the spawn point.

Each probe answers one unknown about how the game loads a glTF file. See
``docs/the-zone-format.md`` for the questions and the recorded answers.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import trimesh

from fpv_maps.materials import (
    checker_image,
    color_material,
    template_material,
    texture_material,
)

GroundFn = Callable[[float, float], float]


def _box(
    extents: tuple[float, float, float], center: tuple[float, float, float]
) -> trimesh.Trimesh:
    box = trimesh.creation.box(extents=extents)
    box.apply_translation(center)
    return box


def _cylinder(
    radius: float, start: np.ndarray, end: np.ndarray, sections: int = 8
) -> trimesh.Trimesh:
    return trimesh.creation.cylinder(radius=radius, segment=[start, end], sections=sections)


def _with_material(mesh: trimesh.Trimesh, material, uv_scale: float = 1.0) -> trimesh.Trimesh:
    """Assign a material with simple planar UVs, so that template textures tile."""
    v = mesh.vertices
    uv = np.column_stack([v[:, 0] + v[:, 2], v[:, 1]]) / uv_scale
    mesh.visual = trimesh.visual.TextureVisuals(uv=uv, material=material)
    return mesh


def build_probes(ground: GroundFn) -> dict[str, trimesh.Trimesh]:
    """Probes in game axes. ``ground(x, z)`` returns the terrain height at a game point."""
    out: dict[str, trimesh.Trimesh] = {}

    # Spawn marker: a thin bright disc at the origin, 5 cm above the ground.
    y0 = ground(0.0, 0.0)
    pad = trimesh.creation.cylinder(radius=2.0, height=0.05, sections=32)
    pad.apply_translation((0.0, y0 + 0.05, 0.0))
    out["probe_spawn_pad"] = _with_material(pad, color_material("fpv_spawn_yellow", (255, 220, 0)))

    # Color material with a name the game does not know.
    x, z = 12.0, -8.0
    y = ground(x, z)
    out["probe_color_box"] = _with_material(
        _box((2.0, 2.0, 2.0), (x, y + 1.0, z)), color_material("fpv_red", (200, 30, 30))
    )

    # Embedded PNG texture on a small box.
    x, z = 12.0, -14.0
    y = ground(x, z)
    out["probe_texture_box"] = _with_material(
        _box((2.0, 2.0, 2.0), (x, y + 1.0, z)),
        texture_material("fpv_checker", checker_image()),
        uv_scale=2.0,
    )

    # Template material by name: the game replaces it with its own brick texture.
    x, z = 12.0, -20.0
    y = ground(x, z)
    out["probe_template_box"] = _with_material(
        _box((2.0, 2.0, 2.0), (x, y + 1.0, z)), template_material("z_rough-brick1"), uv_scale=4.0
    )

    # Wire test: two poles 30 m apart and two wires between them.
    # The first wire is a plain mesh. The second has the Godot ``-col`` suffix.
    # If the game honors the suffix, the second wire is invisible but solid.
    pole_mat = template_material("z_worn-painted-metal")
    wire_mat = color_material("fpv_wire_black", (20, 20, 20), roughness=0.6)
    xa, xb, zw = -15.0, 15.0, 25.0
    ya, yb = ground(xa, zw), ground(xb, zw)
    out["probe_pole_a"] = _with_material(
        _cylinder(0.15, np.array([xa, ya, zw]), np.array([xa, ya + 8.0, zw])), pole_mat
    )
    out["probe_pole_b"] = _with_material(
        _cylinder(0.15, np.array([xb, yb, zw]), np.array([xb, yb + 8.0, zw])), pole_mat
    )
    out["probe_wire"] = _with_material(
        _cylinder(0.01, np.array([xa, ya + 7.5, zw]), np.array([xb, yb + 7.5, zw])), wire_mat
    )
    out["probe_wire-col"] = _with_material(
        _cylinder(0.01, np.array([xa, ya + 6.5, zw]), np.array([xb, yb + 6.5, zw])), wire_mat
    )

    # A gate to fly through: two posts and a top bar, 6 m wide, 4 m high.
    gate_mat = color_material("fpv_gate_orange", (255, 100, 0))
    gx, gz = 0.0, -30.0
    gy = ground(gx, gz)
    out["probe_gate_left"] = _with_material(
        _box((0.3, 4.0, 0.3), (gx - 3.0, gy + 2.0, gz)), gate_mat
    )
    out["probe_gate_right"] = _with_material(
        _box((0.3, 4.0, 0.3), (gx + 3.0, gy + 2.0, gz)), gate_mat
    )
    out["probe_gate_top"] = _with_material(_box((6.3, 0.3, 0.3), (gx, gy + 4.0, gz)), gate_mat)
    return out
