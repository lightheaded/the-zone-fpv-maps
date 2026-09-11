"""Map configuration. One TOML file per map, see the ``maps/`` folder."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from fpv_maps.crs import BBox, wgs84_to_lest97

ORTHO_SOURCES = ("city", "estonia")


@dataclass(frozen=True)
class MapConfig:
    """All settings that the pipeline needs to build one map."""

    name: str
    description: str
    bbox: BBox
    origin: tuple[float, float]
    terrain_step_m: float
    chunk_m: float
    ground_texture_px: int
    ground_texture_source: str
    jpeg_quality: int
    buildings_enabled: bool
    municipalities: tuple[str, ...]
    wall_material: str
    roof_material: str
    probes_enabled: bool
    path: Path

    @property
    def data_dir(self) -> Path:
        return self.path.parent.parent / "data"

    @property
    def dist_dir(self) -> Path:
        return self.path.parent.parent / "dist" / self.name

    @property
    def area_km2(self) -> float:
        return self.bbox.width * self.bbox.height / 1e6


def load_config(path: str | Path) -> MapConfig:
    """Read a map TOML file and resolve the area to an L-EST97 bounding box."""
    path = Path(path).resolve()
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    area = raw["area"]
    if "bbox" in area:
        bbox = BBox(*area["bbox"])
    else:
        lat, lon = area["center_wgs84"]
        east, north = wgs84_to_lest97(lat, lon)
        width, height = area["size_m"]
        bbox = BBox(east - width / 2, north - height / 2, east + width / 2, north + height / 2)

    if "origin_wgs84" in area:
        origin = wgs84_to_lest97(*area["origin_wgs84"])
    elif "origin" in area:
        origin = (float(area["origin"][0]), float(area["origin"][1]))
    else:
        origin = bbox.center

    terrain = raw.get("terrain", {})
    ground = raw.get("ground_texture", {})
    buildings = raw.get("buildings", {})
    probes = raw.get("probes", {})
    chunks = raw.get("chunks", {})

    source = str(ground.get("source", "city"))
    if source not in ORTHO_SOURCES:
        raise ValueError(
            f"ground_texture.source must be one of {sorted(ORTHO_SOURCES)}: {source!r}"
        )

    name = raw["map"]["name"]
    if not name.replace("-", "").replace("_", "").isalnum():
        raise ValueError(f"map name must be letters, digits, - or _: {name!r}")

    buildings_enabled = bool(buildings.get("enabled", True))
    municipalities = tuple(buildings.get("municipalities", ()))
    if buildings_enabled and not municipalities:
        raise ValueError("buildings.municipalities must name the Maa-amet municipality files")

    return MapConfig(
        name=name,
        description=raw["map"].get("description", ""),
        bbox=bbox,
        origin=origin,
        terrain_step_m=float(terrain.get("step_m", 2.0)),
        chunk_m=float(chunks.get("size_m", 0.0)),
        ground_texture_px=int(ground.get("size_px", 8192)),
        ground_texture_source=source,
        jpeg_quality=int(ground.get("jpeg_quality", 88)),
        buildings_enabled=buildings_enabled,
        municipalities=municipalities,
        wall_material=str(buildings.get("wall_material", "z_concrete2")),
        roof_material=str(buildings.get("roof_material", "z_pebbled_asphalt")),
        probes_enabled=bool(probes.get("enabled", False)),
        path=path,
    )
