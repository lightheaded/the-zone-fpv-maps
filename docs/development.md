# Development setup

The pipeline runs on macOS, Windows and Linux. Two ways exist: native with
[uv](https://docs.astral.sh/uv/), and inside [Docker](https://www.docker.com/).
Both install the same locked dependencies. The GPU does not matter for the current
pipeline. It matters for the game, and later for photogrammetry and lidar work.

## Native with uv

1. Install uv. macOS: `brew install uv`. Windows: `winget install astral-sh.uv`.
   Linux: see the uv documentation.
2. Clone the repository and open a terminal in it.
3. Run `uv sync`. This downloads Python 3.12 and the dependencies into `.venv`.
4. Run `uv run pytest`. All tests must pass. They need no network.
5. Run `uv run fpv-maps area maps/annelinn-test.toml` to see the bounding box.

Build the test tile and copy it into the game:

```
uv run fpv-maps build maps/annelinn-test.toml --install
```

The first build downloads about 120 MB into `data/raw/`. Later builds reuse the files.
A build of the test tile takes about 20 seconds on a laptop.

If the game is not in the default Steam folder, set `THE_ZONE_DIR` to the game folder,
or pass `--game-dir`. On Windows, use PowerShell:

```
$env:THE_ZONE_DIR = "D:\SteamLibrary\steamapps\common\The Zone FPV"
uv run fpv-maps install maps/annelinn-test.toml
```

## Docker

Docker Desktop on macOS and Windows, or Docker Engine on Linux. On Windows, Docker
Desktop uses WSL 2. The image builds native on amd64 and arm64.

```
docker compose build
docker compose run --rm pipeline build maps/annelinn-test.toml
```

The container sees `maps/` read only, and writes to `data/` and `dist/` on the host.
To copy the result into the game, run the install step natively, or mount the game
folder:

```
docker compose run --rm -v "$THE_ZONE_DIR:/game" pipeline install maps/annelinn-test.toml --game-dir /game
```

## Test a map in the game

1. Build and install the map.
2. Start The Zone. Open the Play Offline screen. The map appears under custom maps by
   its folder name.
3. Fly to each probe and fill the answer column in `docs/the-zone-format.md`.
4. Do not click Upload until the map is ready for others. The first uploader owns the
   map name.

## Commands

```
uv run fpv-maps --help
uv run fpv-maps area    maps/<name>.toml     # bounding box, origin, map sheets
uv run fpv-maps fetch   maps/<name>.toml     # download source data
uv run fpv-maps build   maps/<name>.toml     # build dist/<name>/<name>.glb
uv run fpv-maps install maps/<name>.toml     # copy into the game
uv run fpv-maps inspect dist/<name>/<name>.glb
```

## Code quality

```
uv run ruff check src tests
uv run ruff format src tests
uv run pytest
```

CI runs the same commands on Linux, macOS and Windows, and builds the Docker image.

## Project layout

```
maps/                 one TOML file per map
src/fpv_maps/
  cli.py              command line, click
  config.py           TOML to MapConfig
  crs.py              L-EST97 to game axes, the only place that converts
  fetch.py            Maa-amet URL patterns, sheet numbers, cached downloads
  geotiff.py          DTM and orthophoto sheets to arrays
  terrain.py          height field to grid mesh with UVs
  buildings.py        LOD2 OBJ to wall and roof meshes
  materials.py        template material names, JPEG and PNG textures
  probes.py           test objects near the spawn point
  export.py           named meshes to one glTF binary file
  inspect.py          statistics of a glTF binary file
  install.py          copy into the game folder
  build.py            the pipeline, step by step
tests/                pytest, synthetic data, no network
docs/                 analysis, decisions, formats, licensing, locations, sources
data/                 downloaded geodata cache, not in git
dist/                 built maps and build reports, not in git
```

## Add a new map

1. Copy `maps/annelinn-test.toml` to `maps/<name>.toml`.
2. Set the name, the bounding box in L-EST97 or a WGS84 center with a size, and the
   municipalities that the box touches.
3. Run `uv run fpv-maps area maps/<name>.toml` and check the sheets.
4. Build, install, fly.

## Data budget

| Data set | Sheet | Size |
|----------|-------|------|
| DTM 1 m GeoTIFF | 5 x 5 km | 60 to 80 MB |
| City orthophoto 10 cm GeoTIFF | 1 x 1 km | 25 to 30 MB zipped |
| Lidar, city flight, LAZ | 1 x 1 km | about 280 MB |
| LOD2 buildings OBJ, Tartu linn | whole city | 12 MB zipped, 64 MB unpacked |
| LOD2 buildings OBJ, Luunja vald | whole parish | 1.4 MB zipped |
| Trees LOD0 GPKG, Tartu linn | whole city | 39 MB zipped |

The whole city needs about 90 orthophoto sheets, 2.5 GB. Keep `data/` on a fast disk.
