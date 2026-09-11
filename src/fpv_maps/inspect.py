"""Statistics of a glTF binary file, with no dependency on a glTF library."""

from __future__ import annotations

import json
import struct
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

GODOT_SUFFIXES = ("-col", "-colonly", "-convcol", "-navmesh", "-rigid", "-noimp", "-occ")


@dataclass
class GlbStats:
    path: str
    size_bytes: int
    generator: str
    nodes: int
    meshes: int
    materials: int
    images: int
    image_bytes: int
    triangles: int
    vertices: int
    bounds_min: list[float]
    bounds_max: list[float]
    node_names: list[str] = field(default_factory=list)
    material_names: list[str] = field(default_factory=list)
    suffixes: dict[str, int] = field(default_factory=dict)
    image_mime_types: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def read_json_chunk(path: Path) -> dict:
    with path.open("rb") as fh:
        magic, _version, _length = struct.unpack("<III", fh.read(12))
        if magic != 0x46546C67:
            raise ValueError(f"{path} is not a glTF binary file")
        chunk_len, _chunk_type = struct.unpack("<II", fh.read(8))
        return json.loads(fh.read(chunk_len))


def inspect_glb(path: Path) -> GlbStats:
    js = read_json_chunk(path)
    accessors = js.get("accessors", [])
    triangles = 0
    vertices = 0
    for mesh in js.get("meshes", []):
        for prim in mesh["primitives"]:
            vertices += accessors[prim["attributes"]["POSITION"]]["count"]
            if "indices" in prim:
                triangles += accessors[prim["indices"]]["count"] // 3
            else:
                triangles += accessors[prim["attributes"]["POSITION"]]["count"] // 3

    mins = []
    maxs = []
    for mesh in js.get("meshes", []):
        for prim in mesh["primitives"]:
            acc = accessors[prim["attributes"]["POSITION"]]
            if "min" in acc and "max" in acc:
                mins.append(acc["min"])
                maxs.append(acc["max"])
    bounds_min = [min(m[i] for m in mins) for i in range(3)] if mins else []
    bounds_max = [max(m[i] for m in maxs) for i in range(3)] if maxs else []

    names = [n.get("name", "") for n in js.get("nodes", [])]
    suffixes = Counter()
    for name in names:
        for s in GODOT_SUFFIXES:
            if name.endswith(s):
                suffixes[s] += 1

    images = js.get("images", [])
    views = js.get("bufferViews", [])
    image_bytes = sum(views[i["bufferView"]]["byteLength"] for i in images if "bufferView" in i)

    return GlbStats(
        path=str(path),
        size_bytes=path.stat().st_size,
        generator=js.get("asset", {}).get("generator", ""),
        nodes=len(js.get("nodes", [])),
        meshes=len(js.get("meshes", [])),
        materials=len(js.get("materials", [])),
        images=len(images),
        image_bytes=image_bytes,
        triangles=triangles,
        vertices=vertices,
        bounds_min=bounds_min,
        bounds_max=bounds_max,
        node_names=names,
        material_names=[m.get("name", "") for m in js.get("materials", [])],
        suffixes=dict(suffixes),
        image_mime_types=dict(Counter(i.get("mimeType", "?") for i in images)),
    )
