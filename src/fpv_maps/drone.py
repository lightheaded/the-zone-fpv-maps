"""Own drone survey products as a map source.

The open data of Maa- ja Ruumiamet covers the whole country at one quality. A survey
flown over one site gives much more detail over much less ground. This module reads
the three products that a DJI Terra project writes and puts them into the same frame
as the rest of the pipeline.

Three differences from the open data decide the code here:

1. **A different projection.** Terra writes UTM zone 35N (EPSG:32635), and the
   pipeline works in L-EST97 (EPSG:3301). Every raster is warped on read.
2. **A different height datum.** Terra writes ellipsoidal heights, and Maa-amet
   writes EH2000. The difference over Estonia is about 19 m, which is enough to put
   an open data building through a drone roof. ``measure_vertical_shift`` measures
   the offset against the open elevation model and the build applies it, so that
   every height in a map is EH2000. The measurement also absorbs an offset of the
   RTK base station, which a fixed geoid model would not.
3. **A textured mesh instead of a building model.** Terra writes the reconstruction
   as 3D Tiles. ``load_mesh_tiles`` reads one level of that pyramid, which is the
   quality knob of a photogrammetry map.

Nothing in this module names a site. The paths come from the map configuration.
"""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import numpy as np
import rasterio
import trimesh
from PIL import Image
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.warp import reproject

from fpv_maps.crs import LEST97, BBox, to_game
from fpv_maps.terrain import HeightField, fill_nodata

ECEF = "EPSG:4978"

#: DJI Terra names a tile ``<block>_L<level>_<index>.b3dm``. A larger level is finer.
TILE_NAME = re.compile(r"_L(\d+)_\d+\.b3dm$")


@dataclass(frozen=True)
class DroneSources:
    """Paths to the products of one survey. Every field is optional but one."""

    elevation: tuple[Path, ...] = ()
    ortho: tuple[Path, ...] = ()
    tileset: Path | None = None
    mesh_elevation: tuple[Path, ...] = ()
    mesh_error_m: float = 0.12
    mesh_texture_px: int = 1024
    mesh_jpeg_quality: int = 85

    def __bool__(self) -> bool:
        return bool(self.elevation or self.ortho or self.tileset)


# --------------------------------------------------------------------------- rasters


def _warp_to_lest97(
    paths: list[Path] | tuple[Path, ...],
    bbox: BBox,
    width: int,
    height: int,
    resampling: Resampling,
    bands: tuple[int, ...],
    fill: float,
    dtype: str = "float32",
) -> np.ndarray:
    """Warp one or more rasters of any projection onto an L-EST97 grid over ``bbox``.

    Returns an array of shape (len(bands), height, width). Row 0 is the north edge.
    Cells that no source covers keep ``fill``.

    ``dtype`` matters for a large image. A 16384 px three band grid is 268 MB as
    ``uint8`` and 3.2 GB as ``float32``, and this function holds two of them at once,
    so a color raster must ask for ``uint8`` or the build runs out of memory. An
    elevation raster stays ``float32``, because it carries real numbers and NaN.
    """
    out = np.full((len(bands), height, width), fill, dtype=dtype)
    patch = np.empty_like(out)
    dst_transform = rasterio.transform.from_bounds(
        bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax, width, height
    )
    for path in paths:
        with rasterio.open(path) as src:
            patch.fill(fill)
            reproject(
                source=rasterio.band(src, list(bands)),
                destination=patch,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=dst_transform,
                dst_crs=LEST97,
                src_nodata=src.nodata,
                dst_nodata=fill,
                resampling=resampling,
            )
            covered = np.isfinite(patch).all(axis=0)
            if np.isfinite(fill):
                covered &= (patch != fill).any(axis=0)
            out[:, covered] = patch[:, covered]
    return out


def read_drone_heights(
    paths: tuple[Path, ...], bbox: BBox, res_m: float, pad_m: float = 4.0
) -> HeightField:
    """A height field over ``bbox`` from drone elevation rasters, sampled every ``res_m``.

    The result is in the height datum of the source. The build shifts it to EH2000
    with ``measure_vertical_shift``.
    """
    if not paths:
        raise ValueError("no drone elevation rasters given")
    box = bbox.buffer(pad_m)
    width = max(2, int(round(box.width / res_m)))
    height = max(2, int(round(box.height / res_m)))
    data = _warp_to_lest97(paths, box, width, height, Resampling.average, (1,), np.nan)
    heights = fill_nodata(data[0], None)
    return HeightField(heights=heights, west=box.xmin, north=box.ymax, res=box.width / width)


def read_drone_rgb(
    paths: tuple[Path, ...], bbox: BBox, size_px: int, base: np.ndarray | None = None
) -> np.ndarray:
    """The drone orthophoto over ``bbox`` as uint8 RGB, ``size_px`` square.

    A survey covers less ground than a map box, so ``base`` is an orthophoto of the
    whole box from the open data. The drone pixels replace it where they exist, and
    the map keeps a picture everywhere instead of a black border.
    """
    if not paths:
        raise ValueError("no drone orthophoto given")
    if base is not None and base.shape != (size_px, size_px, 3):
        raise ValueError(f"base orthophoto is {base.shape}, the map box is {size_px} px square")

    # Warp straight onto the base, band first, and tell rasterio not to clear the
    # destination first. The survey then paints only where it covers ground and the
    # open orthophoto stays everywhere else. Two things fall out of doing it this way.
    # There is one grid in memory instead of two, which is what makes a 16384 px
    # texture buildable. And coverage comes from the footprint of the source rather
    # than from its pixel values, so a genuinely black pixel inside the survey stays
    # black instead of counting as a hole.
    start = np.zeros((3, size_px, size_px), dtype="uint8")
    if base is not None:
        start[:] = np.moveaxis(base, -1, 0)
    dst_transform = rasterio.transform.from_bounds(
        bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax, size_px, size_px
    )
    for path in paths:
        with rasterio.open(path) as src:
            reproject(
                source=rasterio.band(src, [1, 2, 3]),
                destination=start,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=dst_transform,
                dst_crs=LEST97,
                src_nodata=src.nodata,
                resampling=Resampling.average,
                init_dest_nodata=False,
            )
    return np.ascontiguousarray(np.moveaxis(start, 0, -1))


def measure_vertical_shift(
    drone_paths: tuple[Path, ...],
    dtm_paths: list[Path],
    bbox: BBox,
    samples: int = 512,
    bin_m: float = 0.10,
) -> float:
    """Meters to add to a drone height to get EH2000, measured over ``bbox``.

    Two surveys of the same ground do not share a height until someone measures the
    offset. The two flights over this site are 4.1 m apart, because each set its own
    RTK base three months apart, and both are about 19 m above EH2000 because Terra
    writes ellipsoidal heights. Measuring every survey against the same open
    elevation model puts them all in EH2000 and therefore on each other.

    The estimator is the peak of the height difference, not its mean or its median.
    A bare earth model differs from the open model by the datum alone, but a surface
    model also holds roofs and trees, which are real and only ever positive. Those
    pull a mean and a median up. They do not move the peak, because open ground is
    the most common surface of a suburban scene, so the difference has a sharp mode
    at the datum offset. The peak is read from a histogram and then refined with the
    median of the values inside one bin width of it.
    """

    def grid(paths) -> np.ndarray:
        return _warp_to_lest97(paths, bbox, samples, samples, Resampling.average, (1,), np.nan)[0]

    drone = grid(drone_paths)
    open_data = grid(dtm_paths)
    both = np.isfinite(drone) & np.isfinite(open_data)
    if both.sum() < 256:
        raise ValueError("the drone elevation and the open elevation model do not overlap")
    diff = open_data[both] - drone[both]
    edges = np.arange(diff.min(), diff.max() + bin_m, bin_m)
    if edges.size < 3:
        return float(np.median(diff))
    counts, _ = np.histogram(diff, bins=edges)
    peak = edges[int(counts.argmax())] + bin_m / 2
    near = np.abs(diff - peak) <= bin_m
    return float(np.median(diff[near]))


# ------------------------------------------------------------------------ 3D Tiles


def _read_b3dm(path: Path) -> tuple[dict, bytes, int]:
    """The glTF JSON, the whole glTF chunk and the offset of its binary chunk."""
    raw = path.read_bytes()
    magic, _version, _length, ftj, ftb, btj, btb = struct.unpack_from("<4sIIIIII", raw, 0)
    if magic != b"b3dm":
        raise ValueError(f"{path} is not a b3dm tile")
    glb = raw[28 + ftj + ftb + btj + btb :]
    if glb[:4] != b"glTF":
        raise ValueError(f"{path} holds no glTF chunk")
    json_len = struct.unpack_from("<I", glb, 12)[0]
    return json.loads(glb[20 : 20 + json_len]), glb, 20 + json_len + 8


def _accessor(js: dict, glb: bytes, bin_off: int, index: int) -> np.ndarray:
    acc = js["accessors"][index]
    view = js["bufferViews"][acc["bufferView"]]
    dtype = {5121: "u1", 5123: "<u2", 5125: "<u4", 5126: "<f4"}[acc["componentType"]]
    count = acc["count"] * {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[acc["type"]]
    start = bin_off + view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    flat = np.frombuffer(glb, dtype=dtype, count=count, offset=start)
    return flat.reshape(acc["count"], -1)


def _decode_draco(buffer: bytes) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Positions, faces and texture coordinates of one Draco compressed primitive.

    Terra compresses part of the pyramid and leaves the rest plain, so a reader has
    to do both. Draco rebuilds its own vertex list, which is usually a little longer
    than the ``count`` of the glTF accessor, so the decoded arrays are used as they
    come and the accessor is only metadata here.
    """
    try:
        import DracoPy
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on the install
        raise ModuleNotFoundError(
            "this survey holds Draco compressed 3D Tiles. Install the extra with "
            "'uv sync --extra survey'."
        ) from exc
    mesh = DracoPy.decode(buffer)
    return (
        np.asarray(mesh.points, dtype=np.float64),
        np.asarray(mesh.faces, dtype=np.int64).reshape(-1, 3),
        np.asarray(mesh.tex_coord, dtype=np.float64),
    )


def _primitive_arrays(
    js: dict, glb: bytes, bin_off: int, prim: dict
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Positions, faces and texture coordinates of one primitive, compressed or not."""
    draco = prim.get("extensions", {}).get("KHR_draco_mesh_compression")
    if draco is not None:
        view = js["bufferViews"][draco["bufferView"]]
        start = bin_off + view.get("byteOffset", 0)
        return _decode_draco(glb[start : start + view["byteLength"]])
    return (
        _accessor(js, glb, bin_off, prim["attributes"]["POSITION"]).astype(np.float64),
        _accessor(js, glb, bin_off, prim["indices"]).reshape(-1, 3),
        _accessor(js, glb, bin_off, prim["attributes"]["TEXCOORD_0"]).astype(np.float64),
    )


def _tile_texture(
    js: dict, glb: bytes, bin_off: int, index: int, max_px: int, quality: int
) -> Image.Image:
    """One tile texture, re-encoded as JPEG.

    Terra writes WebP. A glTF that holds WebP needs the ``EXT_texture_webp``
    extension, and whether the runtime loader of the game reads it is unknown. JPEG
    is the format that the ground texture already proved in the game. Re-encoding is
    also the texture budget knob: ``max_px`` caps the side of every tile texture.
    """
    view = js["bufferViews"][js["images"][index]["bufferView"]]
    start = bin_off + view.get("byteOffset", 0)
    image = Image.open(BytesIO(glb[start : start + view["byteLength"]])).convert("RGB")
    if max(image.size) > max_px:
        scale = max_px / max(image.size)
        image = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            Image.LANCZOS,
        )
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=quality, optimize=True)
    buf.seek(0)
    out = Image.open(buf)
    out.load()
    return out


def _resolve(node: dict, base: Path) -> tuple[dict, Path]:
    """Follow a child that only links to a sub tileset, and return the node that has a tile.

    Terra writes one JSON file per node of the tree. A child of a node is a link with
    ``content.uri`` ending in ``.json`` and a geometric error of 1e10. The root of
    that file is the real node, and it holds the ``.b3dm`` and the next children.
    """
    uri = node.get("content", {}).get("uri", "")
    while uri.endswith(".json"):
        path = base / uri
        node = json.loads(path.read_text(encoding="utf-8"))["root"]
        base = path.parent
        uri = node.get("content", {}).get("uri", "")
    return node, base


def select_tiles(tileset: Path, max_error_m: float) -> list[tuple[Path, Path]]:
    """Tiles that cover the whole site with a geometric error of at most ``max_error_m``.

    The pyramid refines by REPLACE, so one node and its children show the same ground
    at two qualities. This walk descends while a node is coarser than asked and stops
    at the first node that is good enough, or at a leaf. The result therefore covers
    the site once, with no hole and no double surface.

    A ``max_error_m`` of 0 or less takes every leaf, which is the full survey.
    Returns pairs of (tile path, block folder), because the block folder holds the
    matrix that puts the tile on the earth.
    """
    out: list[tuple[Path, Path]] = []

    def descend(node: dict, base: Path, block: Path) -> None:
        node, base = _resolve(node, base)
        uri = node.get("content", {}).get("uri", "")
        children = node.get("children", [])
        error = float(node.get("geometricError", 0.0))
        good_enough = max_error_m > 0 and error <= max_error_m
        if uri.endswith(".b3dm") and (good_enough or not children):
            out.append((base / uri, block))
            return
        for child in children:
            descend(child, base, block)

    for block in sorted(p for p in tileset.iterdir() if p.is_dir()):
        root_file = block / "tileset.json"
        if not root_file.exists():
            continue
        descend(json.loads(root_file.read_text(encoding="utf-8"))["root"], block, block)
    return out


def tile_levels(tileset: Path) -> dict[int, int]:
    """How many tiles each level of the pyramid holds, over every block."""
    counts: dict[int, int] = {}
    for path in tileset.rglob("*.b3dm"):
        match = TILE_NAME.search(path.name)
        if match:
            level = int(match.group(1))
            counts[level] = counts.get(level, 0) + 1
    return dict(sorted(counts.items()))


def block_transform(block_dir: Path) -> np.ndarray:
    """The 4 x 4 matrix that puts one block of the pyramid into ECEF.

    3D Tiles stores a transform column first. The tiles hold no ``RTC_CENTER``, so
    this matrix alone carries the position of the block on the earth.
    """
    js = json.loads((block_dir / "tileset.json").read_text(encoding="utf-8"))
    return np.array(js["root"]["transform"], dtype=np.float64).reshape(4, 4).T


def load_mesh_tiles(
    tileset: Path,
    max_error_m: float,
    origin: tuple[float, float, float],
    height_shift: float = 0.0,
    max_px: int = 1024,
    quality: int = 85,
    bbox: BBox | None = None,
) -> dict[str, trimesh.Trimesh]:
    """A Terra 3D Tiles pyramid as meshes in game axes, at a chosen geometric error.

    ``max_error_m`` is the quality knob, in meters of surface error. ``max_px`` caps
    the side of every tile texture, which is the second knob. ``height_shift`` is
    added to every height, to bring the ellipsoidal heights of the survey into EH2000.

    Each tile becomes one mesh, because each tile carries its own texture and one
    mesh can hold one texture. A tile outside ``bbox`` is dropped.
    """
    to_lest97 = Transformer.from_crs(ECEF, LEST97, always_xy=True)
    out: dict[str, trimesh.Trimesh] = {}
    for path, block in select_tiles(tileset, max_error_m):
        matrix = block_transform(block)
        js, glb, bin_off = _read_b3dm(path)
        for mesh_index, mesh in enumerate(js["meshes"]):
            for prim_index, prim in enumerate(mesh["primitives"]):
                local, faces, uv = _primitive_arrays(js, glb, bin_off, prim)

                ones = np.ones((len(local), 1))
                ecef = (matrix @ np.hstack([local, ones]).T).T[:, :3]
                east, north, up = to_lest97.transform(ecef[:, 0], ecef[:, 1], ecef[:, 2])
                enh = np.column_stack([east, north, np.asarray(up) + height_shift])
                if bbox is not None and not _touches(enh, bbox):
                    continue

                tri = trimesh.Trimesh(vertices=to_game(enh, origin), faces=faces, process=False)
                material = None
                if "material" in prim:
                    tex = js["materials"][prim["material"]]["pbrMetallicRoughness"]
                    image_index = js["textures"][tex["baseColorTexture"]["index"]]["source"]
                    material = trimesh.visual.material.PBRMaterial(
                        name=f"fpv_mesh_{path.stem}_{mesh_index}_{prim_index}",
                        baseColorTexture=_tile_texture(
                            js, glb, bin_off, image_index, max_px, quality
                        ),
                        metallicFactor=0.0,
                        roughnessFactor=1.0,
                    )
                tri.visual = trimesh.visual.TextureVisuals(uv=uv, material=material)
                out[f"mesh_{path.stem}_{mesh_index}_{prim_index}"] = tri
    return out


def _touches(enh: np.ndarray, bbox: BBox) -> bool:
    """True when the bounding box of ``enh`` overlaps ``bbox``."""
    return bool(
        enh[:, 0].max() >= bbox.xmin
        and enh[:, 0].min() <= bbox.xmax
        and enh[:, 1].max() >= bbox.ymin
        and enh[:, 1].min() <= bbox.ymax
    )
