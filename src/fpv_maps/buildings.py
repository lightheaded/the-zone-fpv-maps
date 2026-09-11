"""Buildings from the Maa-amet LOD2 OBJ export.

The OBJ has no object groups. Each building is one ``usemtl`` block with a generated
name. Coordinates are L-EST97 minus the offset in the ``.fwt`` sidecar file, Z up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import trimesh

from fpv_maps.crs import BBox, to_game

_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")


@dataclass
class Building:
    name: str
    vertices: np.ndarray
    faces: np.ndarray

    @property
    def centroid(self) -> tuple[float, float]:
        c = self.vertices[:, :2].mean(axis=0)
        return float(c[0]), float(c[1])


@dataclass
class BuildingSet:
    buildings: list[Building] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.buildings)

    def extend(self, other: BuildingSet) -> None:
        self.buildings.extend(other.buildings)

    def inside(self, bbox: BBox) -> BuildingSet:
        return BuildingSet([b for b in self.buildings if bbox.contains(*b.centroid)])


def read_offset(fwt_path: Path) -> tuple[float, float, float]:
    """Read the (east, north, height) offset from a Maa-amet ``.fwt`` sidecar file.

    FME writes a 3 x 4 matrix, one row per axis, with the offset in the last column::

        1 0 0 654513.288
        0 1 0 6475676.235
        0 0 1 62.645

    A file with three plain numbers is also accepted.
    """
    rows = [
        [float(x) for x in _NUMBER.findall(line)]
        for line in fwt_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) == 3 and all(len(r) == 4 for r in rows):
        return rows[0][3], rows[1][3], rows[2][3]
    flat = [x for r in rows for x in r]
    if len(flat) == 3:
        return flat[0], flat[1], flat[2]
    raise ValueError(f"unexpected offset file format in {fwt_path}: {rows}")


def _triangulate(face: list[int]) -> list[tuple[int, int, int]]:
    """Fan triangulation. LOD2 faces are planar and nearly always convex."""
    return [(face[0], face[i], face[i + 1]) for i in range(1, len(face) - 1)]


def read_obj(path: Path, offset: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> BuildingSet:
    """Stream an OBJ file and split it into one Building per ``usemtl`` block."""
    vertices: list[tuple[float, float, float]] = []
    buildings: list[Building] = []
    current_name: str | None = None
    current_faces: list[tuple[int, int, int]] = []

    def flush() -> None:
        if current_name is None or not current_faces:
            return
        faces = np.asarray(current_faces, dtype=np.int64)
        used = np.unique(faces)
        remap = np.full(len(vertices), -1, dtype=np.int64)
        remap[used] = np.arange(len(used))
        verts = np.asarray([vertices[i] for i in used], dtype=np.float64)
        buildings.append(Building(current_name, verts, remap[faces]))

    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("v "):
                parts = line.split()
                vertices.append(
                    (
                        float(parts[1]) + offset[0],
                        float(parts[2]) + offset[1],
                        float(parts[3]) + offset[2],
                    )
                )
            elif line.startswith("f "):
                idx = [int(p.split("/")[0]) - 1 for p in line.split()[1:]]
                current_faces.extend(_triangulate(idx))
            elif line.startswith("usemtl "):
                flush()
                current_name = line.split(maxsplit=1)[1].strip()
                current_faces = []
    flush()
    return BuildingSet(buildings)


def _face_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    a = vertices[faces[:, 0]]
    b = vertices[faces[:, 1]]
    c = vertices[faces[:, 2]]
    n = np.cross(b - a, c - a)
    length = np.linalg.norm(n, axis=1, keepdims=True)
    length[length == 0] = 1.0
    return n / length


def _planar_uv(vertices: np.ndarray, normals_per_vertex: np.ndarray, scale: float) -> np.ndarray:
    """World space UVs in meters divided by ``scale``. Walls use (along, up), roofs (x, z)."""
    x, y, z = vertices[:, 0], vertices[:, 1], vertices[:, 2]
    ny = np.abs(normals_per_vertex[:, 1])
    nx = np.abs(normals_per_vertex[:, 0])
    u_roof, v_roof = x, z
    u_wall = np.where(nx > 0.5, z, x)
    v_wall = y
    u = np.where(ny > 0.5, u_roof, u_wall) / scale
    v = np.where(ny > 0.5, v_roof, v_wall) / scale
    return np.column_stack([u, v])


def build_building_meshes(
    buildings: BuildingSet,
    origin: tuple[float, float, float],
    wall_material: str,
    roof_material: str,
    uv_scale_m: float = 4.0,
) -> dict[str, trimesh.Trimesh]:
    """Merge all buildings into two meshes, walls and roofs, in game axes.

    A face is a roof when its normal points up more than 30 degrees. Faces are
    unwelded so that each face gets its own material and UVs.
    """
    from fpv_maps.materials import template_material

    wall_tris: list[np.ndarray] = []
    roof_tris: list[np.ndarray] = []
    for b in buildings.buildings:
        verts = to_game(b.vertices, origin)
        faces = b.faces
        n = _face_normals(verts, faces)
        is_roof = n[:, 1] > 0.5
        tri = verts[faces]  # (F, 3, 3)
        wall_tris.append(tri[~is_roof])
        roof_tris.append(tri[is_roof])

    out: dict[str, trimesh.Trimesh] = {}
    for key, tris, mat in (
        ("walls", wall_tris, wall_material),
        ("roofs", roof_tris, roof_material),
    ):
        if not tris:
            continue
        stacked = np.concatenate(tris) if tris else np.zeros((0, 3, 3))
        if len(stacked) == 0:
            continue
        verts = stacked.reshape(-1, 3)
        faces = np.arange(len(verts)).reshape(-1, 3)
        normals = np.repeat(_face_normals(verts, faces), 3, axis=0)
        mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
        mesh.visual = trimesh.visual.TextureVisuals(
            uv=_planar_uv(verts, normals, uv_scale_m), material=template_material(mat)
        )
        out[key] = mesh
    return out
