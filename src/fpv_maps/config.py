"""Map configuration. One TOML file per map, see the ``maps/`` folder."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from fpv_maps.course import Gate
from fpv_maps.crs import BBox, wgs84_to_lest97
from fpv_maps.drone import DroneSources

ORTHO_SOURCES = ("city", "estonia")


@dataclass(frozen=True)
class MapConfig:
    """All settings that the pipeline needs to build one map."""

    name: str
    description: str
    bbox: BBox
    origin: tuple[float, float]
    terrain_step_m: float
    terrain_sink_m: float
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
    drone: DroneSources = field(default_factory=DroneSources)
    gates: tuple[Gate, ...] = ()

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

    drone = _load_drone(raw.get("drone", {}), path.parent)
    gates = _load_gates(raw.get("course", {}))

    return MapConfig(
        name=name,
        description=raw["map"].get("description", ""),
        bbox=bbox,
        origin=origin,
        terrain_step_m=float(terrain.get("step_m", 2.0)),
        terrain_sink_m=float(terrain.get("sink_m", 0.0)),
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
        drone=drone,
        gates=gates,
    )


def _paths(value, base: Path) -> tuple[Path, ...]:
    """One path or a list of them, resolved against the folder of the map file."""
    if value is None:
        return ()
    items = [value] if isinstance(value, str) else list(value)
    return tuple((base / Path(p).expanduser()).resolve() for p in items)


def _load_drone(raw: dict, base: Path) -> DroneSources:
    """The ``[drone]`` section: products of an own survey, outside the open data.

    Paths are relative to the map file. The pipeline never downloads these, because
    they are not published anywhere. A map that names a missing file fails the build
    rather than falling back to the open data, so a quality claim is never silent.
    """
    if not raw:
        return DroneSources()
    tileset = raw.get("mesh_tileset")
    sources = DroneSources(
        elevation=_paths(raw.get("elevation"), base),
        ortho=_paths(raw.get("ortho"), base),
        tileset=_paths(tileset, base)[0] if tileset else None,
        mesh_elevation=_paths(raw.get("mesh_elevation"), base),
        mesh_error_m=float(raw.get("mesh_error_m", 0.12)),
        mesh_texture_px=int(raw.get("mesh_texture_px", 1024)),
        mesh_jpeg_quality=int(raw.get("mesh_jpeg_quality", 85)),
    )
    for path in (*sources.elevation, *sources.ortho, *sources.mesh_elevation):
        if not path.exists():
            raise FileNotFoundError(f"drone source is missing: {path}")
    if sources.tileset is not None and not sources.tileset.is_dir():
        raise FileNotFoundError(f"drone mesh tileset is missing: {sources.tileset}")
    return sources


def _load_gates(raw: dict) -> tuple[Gate, ...]:
    """The ``[course]`` section: a list of gates in L-EST97, in the order to fly them."""
    out = []
    defaults = {
        "height_m": float(raw.get("height_m", 6.0)),
        "size_m": float(raw.get("size_m", 5.0)),
    }
    for gate in raw.get("gate", ()):
        east, north = gate["at"]
        out.append(
            Gate(
                east=float(east),
                north=float(north),
                height_m=float(gate.get("height_m", defaults["height_m"])),
                size_m=float(gate.get("size_m", defaults["size_m"])),
                yaw_deg=float(gate.get("yaw_deg", 0.0)),
            )
        )
    return tuple(out)
