"""Map configuration. One TOML file per map, see the ``maps/`` folder."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from fpv_maps.course import Gate
from fpv_maps.crs import BBox, wgs84_to_lest97
from fpv_maps.drone import DroneSources

ORTHO_SOURCES = ("city", "estonia")
ROOF_SOURCES = ("material", "orthophoto")


@dataclass(frozen=True)
class LidarSettings:
    """The ``[lidar]`` section: build the surface from the laser scan itself.

    With this on, the terrain mesh is the highest laser return in every cell rather
    than the bare earth model, so the trees, the roofs and the masts are in the mesh
    as measured. ``res_m`` is the cell size of that surface, and the terrain step
    should match it: a step finer than the scan invents detail, and a step coarser
    than the scan throws it away.

    ``colour`` textures the map from the colour of the points instead of the
    orthophoto. The scan has about one point per 20 cm against 10 cm orthophoto
    pixels, so it is the softer of the two, and it is the only one that puts the right
    colour on a wall rather than smearing the roof down it.
    """

    enabled: bool = False
    res_m: float = 0.5
    colour: bool = False
    classes: tuple[int, ...] = ()
    #: Point cloud files to read. Empty downloads the Maa-amet sheets for the box.
    #: Name files here to use a survey of your own, in any format laspy reads.
    files: tuple[Path, ...] = ()
    #: The projection the named files are in, if it is not L-EST97. Reprojected on read.
    crs: str = ""
    #: Metres to add to every height. Empty measures it against the open elevation
    #: model, which puts an ellipsoidal survey into EH2000 and absorbs a base station
    #: offset at the same time. Set a number to skip the measurement.
    height_shift_m: float | None = None
    #: Radius in cells of the closing that turns woodland from spikes into canopy.
    #: See ``lidar.close_gaps``. Zero is the raw highest return.
    close_cells: int = 2
    #: Radius in cells of a mean filter after the closing. One cell is usually enough.
    smooth_cells: int = 1


@dataclass(frozen=True)
class FacadeSettings:
    """The ``[facades]`` section: wall textures from oblique photos.

    ``level`` is the Deep Zoom level of the photo service. Level 12 is half of the
    full frame, which is about 18 cm on a wall at the usual flight height. ``texel_m``
    is how fine the atlas samples a wall; below the photo resolution it only makes the
    file bigger. ``atlas_px`` is the width of the atlas, which grows in height until
    every panel fits.
    """

    enabled: bool = False
    level: int = 12
    texel_m: float = 0.20
    atlas_px: int = 8192
    max_candidates: int = 34
    max_sources: int = 14
    min_correlation: float = 0.30
    jpeg_quality: int = 85


@dataclass(frozen=True)
class MapConfig:
    """All settings that the pipeline needs to build one map."""

    name: str
    description: str
    #: ``[map] private``. This map is built but never published: no release asset, no
    #: wiki page, no screenshot. Two reasons lead here and both end the same way. The
    #: map is over a private site, or an input may not be redistributed. The build
    #: report of a private map is redacted, and the release and preview checks skip it.
    private: bool
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
    #: ``[buildings] roof_source``. ``material`` gives every roof the same in-game
    #: asphalt. ``orthophoto`` gives each roof its own picture from straight above,
    #: which is the single largest visual gain available to a map of open data.
    roof_source: str
    probes_enabled: bool
    path: Path
    facades: FacadeSettings = field(default_factory=FacadeSettings)
    lidar: LidarSettings = field(default_factory=LidarSettings)
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
    facades = _load_facades(raw.get("facades", {}))
    lidar = _load_lidar(raw.get("lidar", {}), path.parent)
    chunks = raw.get("chunks", {})

    source = str(ground.get("source", "city"))
    if source not in ORTHO_SOURCES:
        raise ValueError(
            f"ground_texture.source must be one of {sorted(ORTHO_SOURCES)}: {source!r}"
        )

    roof_source = str(buildings.get("roof_source", "material"))
    if roof_source not in ROOF_SOURCES:
        raise ValueError(
            f"buildings.roof_source must be one of {sorted(ROOF_SOURCES)}: {roof_source!r}"
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
        private=bool(raw["map"].get("private", False)),
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
        roof_source=roof_source,
        probes_enabled=bool(probes.get("enabled", False)),
        path=path,
        facades=facades,
        lidar=lidar,
        drone=drone,
        gates=gates,
    )


def _load_lidar(raw: dict, base: Path) -> LidarSettings:
    """The ``[lidar]`` section. Absent or ``enabled = false`` uses the terrain model."""
    if not raw:
        return LidarSettings()
    settings = LidarSettings(
        enabled=bool(raw.get("enabled", True)),
        res_m=float(raw.get("res_m", 0.5)),
        colour=bool(raw.get("colour", False)),
        classes=tuple(int(c) for c in raw.get("classes", ())),
        files=_paths(raw.get("files"), base),
        crs=str(raw.get("crs", "")),
        height_shift_m=(float(raw["height_shift_m"]) if "height_shift_m" in raw else None),
        close_cells=int(raw.get("close_cells", 2)),
        smooth_cells=int(raw.get("smooth_cells", 1)),
    )
    if settings.res_m <= 0:
        raise ValueError(f"lidar.res_m must be positive: {settings.res_m}")
    for path in settings.files:
        if not path.exists():
            raise FileNotFoundError(f"lidar point cloud is missing: {path}")
    return settings


def _load_facades(raw: dict) -> FacadeSettings:
    """The ``[facades]`` section. Absent or ``enabled = false`` keeps template walls."""
    if not raw:
        return FacadeSettings()
    settings = FacadeSettings(
        enabled=bool(raw.get("enabled", True)),
        level=int(raw.get("level", 12)),
        texel_m=float(raw.get("texel_m", 0.20)),
        atlas_px=int(raw.get("atlas_px", 8192)),
        max_candidates=int(raw.get("max_candidates", 34)),
        max_sources=int(raw.get("max_sources", 14)),
        min_correlation=float(raw.get("min_correlation", 0.30)),
        jpeg_quality=int(raw.get("jpeg_quality", 85)),
    )
    if not 8 <= settings.level <= 14:
        raise ValueError(f"facades.level is a Deep Zoom level, 8 to 14: {settings.level}")
    if settings.texel_m <= 0:
        raise ValueError(f"facades.texel_m must be positive: {settings.texel_m}")
    if settings.atlas_px > 16384:
        raise ValueError(f"facades.atlas_px must not exceed 16384: {settings.atlas_px}")
    return settings


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
