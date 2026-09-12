"""Collect the build reports of a family of maps into one table.

A benchmark needs two halves. The build writes the first half, which is what a map
costs: triangles, meshes, texture memory and file size. A person flying the map
writes the second half, which is what the machine does with it. This module reads the
first half out of ``dist/<name>/<name>-build-report.json`` and prints a table with an
empty column for the second, so that the numbers land beside each other.

The video memory estimate follows ``docs/analysis.md``: four bytes per pixel plus one
third for the mip chain. That is the worst case of a runtime glTF loader, which keeps
no compressed format on the GPU.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

#: Bytes per texture pixel in video memory, with the mip chain.
BYTES_PER_PIXEL = 4 * 4 / 3


@dataclass(frozen=True)
class MapCost:
    """What one built map costs, read from its build report and its glTF statistics."""

    name: str
    area_m: float
    triangles: int
    meshes: int
    materials: int
    images: int
    texture_px: int
    file_mb: float
    image_mb: float
    ground_cm_per_px: float
    terrain_step_m: float
    mesh_error_m: float | None
    mesh_texture_px: int | None
    lap_m: float | None
    blocked_gates: list[int]

    @property
    def vram_gb(self) -> float:
        return self.texture_px * BYTES_PER_PIXEL / 2**30


def _texture_pixels(report: dict) -> int:
    """Total texture pixels of a map.

    The build report holds the byte size of the embedded images, not their pixel
    count, so the ground texture is computed from its side and the survey tiles are
    counted at the cap that the build applied. A tile whose texture was already
    smaller than the cap therefore counts too high, so this is an upper bound.
    """
    total = report["ground_texture_px"] ** 2
    survey = report.get("survey_mesh")
    if survey:
        total += survey["meshes_in_box"] * survey["texture_px_cap"] ** 2
    return total


def read_cost(report_path: Path) -> MapCost:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    glb = report["glb"]
    survey = report.get("survey_mesh")
    course = report.get("course", {})
    bbox = report["bbox_lest97"]
    return MapCost(
        name=report["map"],
        area_m=bbox[2] - bbox[0],
        triangles=glb["triangles"],
        meshes=glb["meshes"],
        materials=glb["materials"],
        images=glb["images"],
        texture_px=_texture_pixels(report),
        file_mb=glb["size_bytes"] / 1e6,
        image_mb=glb["image_bytes"] / 1e6,
        ground_cm_per_px=report["ground_texture_m_per_px"] * 100,
        terrain_step_m=report["terrain_step_m"],
        mesh_error_m=survey["max_error_m"] if survey else None,
        mesh_texture_px=survey["texture_px_cap"] if survey else None,
        lap_m=course.get("lap_length_m"),
        blocked_gates=course.get("blocked_gates", []),
    )


def collect(dist: Path, names: list[str]) -> list[MapCost]:
    """Costs of the named maps, in the order given. A map with no report is skipped."""
    out = []
    for name in names:
        report = dist / name / f"{name}-build-report.json"
        if report.exists():
            out.append(read_cost(report))
    return out


def markdown_table(costs: list[MapCost]) -> str:
    """The cost table, with an empty column per machine for the measured frame rate."""
    head = (
        "| Map | Box | Mesh error | Tile texture | Terrain | Ground px | Triangles "
        "| Meshes | Images | File | Texture VRAM | FPS laptop | FPS desktop |"
    )
    rule = "|" + "---|" * 13
    rows = [head, rule]
    for c in costs:
        error = f"{c.mesh_error_m:.2f} m" if c.mesh_error_m is not None else "-"
        cap = f"{c.mesh_texture_px} px" if c.mesh_texture_px is not None else "-"
        rows.append(
            f"| `{c.name}` | {c.area_m:.0f} m | {error} | {cap} | {c.terrain_step_m:.2f} m "
            f"| {c.ground_cm_per_px:.1f} cm | {c.triangles:,} | {c.meshes} | {c.images} "
            f"| {c.file_mb:.0f} MB | {c.vram_gb:.2f} GB | | |"
        )
    return "\n".join(rows)
