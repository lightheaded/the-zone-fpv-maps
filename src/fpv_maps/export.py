"""Assemble named meshes into one glTF binary file."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh


def flip_uv_for_export(mesh: trimesh.Trimesh) -> None:
    """Turn a glTF texture coordinate into the one trimesh must be handed. In place.

    The pipeline numbers V the glTF way everywhere: V = 0 reads row 0 of the image,
    and row 0 of an orthophoto is north. trimesh holds V the OpenGL way, V = 0 at the
    bottom of the image, and its glTF exporter writes ``1 - V``. Handing it a glTF V
    therefore ships a file with every texture upside down.

    The flip belongs here, in the one place where meshes become a file, and not in
    each producer of texture coordinates. Two things make that worth insisting on.
    The terrain, the buildings, the probes, the course and the survey mesh all make
    their own UVs, so a per producer flip is five chances to forget. And a reader
    built on trimesh cannot see the fault at all: trimesh flips again on import, so a
    round trip through it is clean while the shipped file is mirrored. That is what
    hid this for two releases, and it is why ``tests/test_export.py`` reads the bytes
    of the file rather than loading it.
    """
    visual = getattr(mesh, "visual", None)
    uv = getattr(visual, "uv", None)
    if uv is None:
        return
    flipped = np.array(uv, dtype=np.float64, copy=True)
    flipped[:, 1] = 1.0 - flipped[:, 1]
    visual.uv = flipped


def write_glb(meshes: dict[str, trimesh.Trimesh], path: Path) -> int:
    """Write ``meshes`` as one scene. Keys become node and mesh names. Returns the byte size.

    The texture coordinates of ``meshes`` are flipped in place, so the meshes are
    spent afterwards. Nothing in the pipeline reads them after the export.
    """
    scene = trimesh.Scene()
    for name, mesh in meshes.items():
        flip_uv_for_export(mesh)
        scene.add_geometry(mesh, node_name=name, geom_name=name)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = scene.export(file_type="glb")
    path.write_bytes(data)
    return len(data)
