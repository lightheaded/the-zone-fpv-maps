"""Assemble named meshes into one glTF binary file."""

from __future__ import annotations

from pathlib import Path

import trimesh


def write_glb(meshes: dict[str, trimesh.Trimesh], path: Path) -> int:
    """Write ``meshes`` as one scene. Keys become node and mesh names. Returns the byte size."""
    scene = trimesh.Scene()
    for name, mesh in meshes.items():
        scene.add_geometry(mesh, node_name=name, geom_name=name)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = scene.export(file_type="glb")
    path.write_bytes(data)
    return len(data)
