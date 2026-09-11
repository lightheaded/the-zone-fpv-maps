"""Download Maa- ja Ruumiamet open data for a bounding box, with a local cache.

Every direct download has the form::

    https://geoportaal.maaamet.ee/index.php?lang_id=1&plugin_act=otsing
        &kaardiruut=<SHEET>&andmetyyp=<CODE>&dl=1&f=<FILENAME>&page_id=<PAGE>

Sheet numbers are L-EST97 kilometer coordinates of the south west corner:

- 1:2000 grid, 1 x 1 km, six digits: ``473662`` is north 6 473 000, east 662 000.
  Used by lidar, DSM and the 10 cm city orthophoto.
- 1:10000 grid, 5 x 5 km, five digits: ``54761`` is the 10 km block 54.76 plus the
  quadrant 1 = SW, 2 = SE, 3 = NW, 4 = NE. Used by the DTM and the 20 cm orthophoto.

The file names for the orthophoto carry the flight date, so the pipeline asks the
search endpoint for the file list of a sheet and picks the newest GeoTIFF.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import httpx
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TransferSpeedColumn,
)

from fpv_maps.crs import BBox

BASE_URL = "https://geoportaal.maaamet.ee/index.php"
LICENSE_URL = "https://geoportaal.maaruum.ee/opendata-licence"
USER_AGENT = "the-zone-fpv-maps (https://github.com/lightheaded/the-zone-fpv-maps)"


@dataclass(frozen=True)
class Product:
    """One downloadable data set."""

    key: str
    code: str
    page_id: int
    grid: int | None  # 2000, 10000 or None for whole area files


DTM_1M = Product("dtm_1m", "dem_1m_geotiff", 614, 10000)
DSM_1M = Product("dsm_1m", "ndsm_abs_1m_geotiff", 614, 2000)
ORTHO_CITY_RGB = Product("ortho_city_rgb", "ortofoto_asulad_rgb", 610, 2000)
ORTHO_EESTI_RGB = Product("ortho_eesti_rgb", "ortofoto_eesti_rgb", 610, 10000)
LIDAR_MADAL = Product("lidar_madal", "lidar_laz_madal", 614, 2000)
BUILDINGS_LOD2 = Product("lod2", "hooned_lod2", 833, None)
TREES_LOD0 = Product("trees", "vegetatsioon", 833, None)


def sheet_2000(east: float, north: float) -> str:
    return f"{int(north // 1000) - 6000:03d}{int(east // 1000):03d}"


def sheet_10000(east: float, north: float) -> str:
    """Five digit 1:10000 sheet number, verified against the Maa-amet grid file.

    Digits: 100 km row, 100 km column, 10 km row, 10 km column, then the quadrant
    of the 10 km block: 1 = SW, 2 = SE, 3 = NW, 4 = NE.
    """
    block = (
        f"{int(north // 100000) - 59}{int(east // 100000) - 2}"
        f"{int(north // 10000) % 10}{int(east // 10000) % 10}"
    )
    east_half = (east % 10000) >= 5000
    north_half = (north % 10000) >= 5000
    quadrant = 1 + (1 if east_half else 0) + (2 if north_half else 0)
    return f"{block}{quadrant}"


def sheets_for(bbox: BBox, grid: int) -> list[str]:
    """All sheets of ``grid`` that intersect ``bbox``. A point on a shared edge counts once."""
    size = 1000 if grid == 2000 else 5000
    fn = sheet_2000 if grid == 2000 else sheet_10000
    eps = 1e-6
    sheets: list[str] = []
    east = bbox.xmin
    while east < bbox.xmax - eps:
        north = bbox.ymin
        while north < bbox.ymax - eps:
            sheets.append(fn(east, north))
            north = (int(north // size) + 1) * size
        east = (int(east // size) + 1) * size
    return sorted(set(sheets))


def download_url(product: Product, filename: str, sheet: str | None = None) -> str:
    params = {"lang_id": 1, "plugin_act": "otsing"}
    if sheet:
        params["kaardiruut"] = sheet
    params.update({"andmetyyp": product.code, "dl": 1, "f": filename, "page_id": product.page_id})
    return f"{BASE_URL}?{urlencode(params)}"


def search_url(product: Product, sheet: str) -> str:
    params = {
        "lang_id": 1,
        "plugin_act": "otsing",
        "page_id": product.page_id,
        "kaardiruut": sheet,
        "andmetyyp": product.code,
    }
    return f"{BASE_URL}?{urlencode(params)}"


_FILE_PARAM = re.compile(r"[?&;]f=([A-Za-z0-9_.\-]+)")


def list_files(client: httpx.Client, product: Product, sheet: str) -> list[str]:
    """File names that the sheet search lists for one product."""
    resp = client.get(search_url(product, sheet))
    resp.raise_for_status()
    names = _FILE_PARAM.findall(resp.text.replace("&amp;", "&"))
    return sorted(set(names))


def newest_geotiff(files: list[str]) -> str | None:
    """The newest ``*_GeoTIFF_<date>.zip`` in a list. Dates in the name sort as text."""
    tifs = [f for f in files if "GeoTIFF" in f and f.endswith(".zip")]
    return max(tifs) if tifs else None


class Fetcher:
    """Download files into ``data/raw/<product>/`` and skip files that exist."""

    def __init__(self, data_dir: Path, quiet: bool = False):
        self.raw = data_dir / "raw"
        self.quiet = quiet
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=httpx.Timeout(60.0), follow_redirects=True
        )

    def close(self) -> None:
        self.client.close()

    def target(self, product: Product, filename: str) -> Path:
        return self.raw / product.key / filename

    def download(self, url: str, dest: Path, label: str) -> Path:
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        with self.client.stream("GET", url) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0)) or None
            with (
                Progress(
                    TextColumn("{task.description}"),
                    BarColumn(),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    disable=self.quiet,
                ) as progress,
                tmp.open("wb") as fh,
            ):
                task = progress.add_task(label, total=total)
                for chunk in resp.iter_bytes(1 << 20):
                    fh.write(chunk)
                    progress.update(task, advance=len(chunk))
        if tmp.stat().st_size == 0:
            tmp.unlink()
            raise RuntimeError(f"empty download: {url}")
        tmp.replace(dest)
        return dest

    def fetch(self, product: Product, filename: str, sheet: str | None = None) -> Path:
        return self.download(
            download_url(product, filename, sheet), self.target(product, filename), filename
        )

    def fetch_sheet_newest_geotiff(self, product: Product, sheet: str) -> Path:
        files = list_files(self.client, product, sheet)
        name = newest_geotiff(files)
        if name is None:
            raise FileNotFoundError(f"no GeoTIFF for {product.key} sheet {sheet}: {files}")
        return self.fetch(product, name, sheet)

    def fetch_dtm(self, bbox: BBox) -> list[Path]:
        return [self.fetch(DTM_1M, f"{s}_dtm_1m.tif", s) for s in sheets_for(bbox, 10000)]

    def fetch_ortho_city(self, bbox: BBox) -> list[Path]:
        paths = []
        for sheet in sheets_for(bbox, 2000):
            zip_path = self.fetch_sheet_newest_geotiff(ORTHO_CITY_RGB, sheet)
            paths.extend(extract(zip_path, suffixes=(".tif", ".tfw")))
        return [p for p in paths if p.suffix.lower() == ".tif"]

    def fetch_lod2(self, municipality: str) -> tuple[Path, Path]:
        """Return the OBJ path and the ``.fwt`` offset file for one municipality.

        Names follow the Maa-amet files: ``Tartu_linn``, ``Luunja_vald``.
        """
        zip_path = self.fetch(BUILDINGS_LOD2, f"hooned_lod2-{municipality}-obj.zip")
        files = extract(zip_path, suffixes=(".obj", ".fwt"))
        obj = next(p for p in files if p.suffix.lower() == ".obj")
        fwt = next(p for p in files if p.suffix.lower() == ".fwt")
        return obj, fwt


def extract(zip_path: Path, suffixes: tuple[str, ...]) -> list[Path]:
    """Unzip the members with ``suffixes`` next to the zip, into a folder with its stem."""
    out_dir = zip_path.with_suffix("")
    out: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            if member.is_dir() or not member.filename.lower().endswith(suffixes):
                continue
            target = out_dir / Path(member.filename).name
            if not target.exists():
                out_dir.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, target.open("wb") as dst:
                    while chunk := src.read(1 << 20):
                        dst.write(chunk)
            out.append(target)
    return out
