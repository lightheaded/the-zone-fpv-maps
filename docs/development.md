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
5. Run `uv run fpv-maps area maps/tartu-annelinn-test.toml` to see the bounding box.

Build the test tile and copy it into the game:

```
uv run fpv-maps build maps/tartu-annelinn-test.toml --install
```

The first build downloads about 120 MB into `data/raw/`. Later builds reuse the files.
A build of the test tile takes about 6 seconds on a laptop.

The base map of the whole city is larger. Its first build downloads 1.6 GB, keeps
2.8 GB on disk after the zip files are unpacked, and needs about 3 GB of memory.
The build itself takes about 11 seconds.

```
uv run fpv-maps build maps/tartu.toml --install
```

If the game is not in the default Steam folder, set `THE_ZONE_DIR` to the game folder,
or pass `--game-dir`. On Windows, use PowerShell:

```
$env:THE_ZONE_DIR = "D:\SteamLibrary\steamapps\common\The Zone FPV"
uv run fpv-maps install maps/tartu-annelinn-test.toml
```

## Docker

Docker Desktop on macOS and Windows, or Docker Engine on Linux. On Windows, Docker
Desktop uses WSL 2. The image builds native on amd64 and arm64.

```
docker compose build
docker compose run --rm pipeline build maps/tartu-annelinn-test.toml
```

The container sees `maps/` read only, and writes to `data/` and `dist/` on the host.
To copy the result into the game, run the install step natively, or mount the game
folder:

```
docker compose run --rm -v "$THE_ZONE_DIR:/game" pipeline install maps/tartu-annelinn-test.toml --game-dir /game
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
uv run fpv-maps tour    maps/<name>.toml     # tour pictures and a tour video
uv run fpv-maps shots   maps/<name>.toml <folder>   # import in-game screenshots
uv run fpv-maps gallery                      # write the wiki pages
```

## Pictures of a map

A map carries three kinds of picture. All three live in `docs/screenshots/`.

| Picture | File | Who makes it |
|---------|------|--------------|
| Preview, from above | `<name>-preview.jpg` | `fpv-maps build` |
| Tour, one per shot | `<name>-tour-<n>-<shot>.jpg` | `fpv-maps tour` |
| In the game | `<name>-ingame-<n>.jpg` | a person, then `fpv-maps shots` |

### The tour

The renderer is an optional extra, because [moderngl](https://moderngl.readthedocs.io/) needs a C++ compiler on Linux
and Windows. Install it once:

```
uv sync --extra tour
```

`fpv-maps tour maps/<name>.toml` flies a camera over `dist/<name>/<name>.glb` and
renders every frame with an offscreen OpenGL context. It writes one JPEG per shot and
one MP4 into `dist/<name>/tour/`. `--publish` copies the JPEG files into
`docs/screenshots/`. The video never goes into git. See `docs/decisions.md`.

```
uv run fpv-maps tour maps/tartu-vaksali.toml --publish
uv run fpv-maps tour maps/tartu-vaksali.toml --shot tartu-mill --no-video   # one shot, fast
uv run fpv-maps tour maps/tartu-vaksali.toml --size 1280x720 --fps 30       # a quick look
```

A map that declares no `[tour]` section gets an automatic tour: a wide orbit, an orbit
around each of the two tallest structures, and a reveal at the spawn point. To choose
the shots, add a `[tour]` section. `maps/tartu-vaksali.toml` is the example. A target is
L-EST97 (east, north), or WGS84 with the key `target_wgs84`. The kinds are:

- `orbit`: a circle around a target, at `radius_m` and `height_m` above the terrain.
- `reveal`: the camera rises and pulls back from the target.
- `fly`: a straight line from `start` to `end`, looking ahead.

Speed on a workstation GPU, at 1920 x 1080: 43 to 80 frames per second, so a tour of
50 seconds takes about one minute. The renderer needs an OpenGL 3.3 context. macOS,
Windows and Linux with a GPU driver give one. The container has Mesa, which draws the
same picture in software at about 5 frames per second at 320 x 180. Use the container
to check that the renderer runs, not to render a release. A build agent has no GPU, so
CI never renders a tour.

### In-game screenshots

The game has no free camera and no command line option that loads a map, so a person
flies the map and captures the pictures. Then:

```
uv run fpv-maps shots maps/tartu-vaksali.toml ~/Pictures/raw-captures
```

The command scales every picture to 1600 px, drops the metadata and writes
`docs/screenshots/<name>-ingame-<n>.jpg`. The oldest picture becomes number one. The
metadata of a screenshot can name a user and a machine, so it never reaches the
repository. Use `--append` to add pictures to a map that has some.

### The wiki

`fpv-maps gallery` writes the wiki pages into `dist/wiki/`:

- `Home.md`, the index, with one row and one picture per map.
- `<name>.md`, one page per map, with every picture of that map.
- `_Sidebar.md` and `_Footer.md`, the navigation and the attribution.

Every picture is linked from the repository, so the wiki holds no second copy. Every
video is linked from the newest release. The pages are generated, so never edit them in
the wiki.

```
scripts/publish-tours.sh v0.4.0              # videos and wiki pages
scripts/publish-tours.sh v0.4.0 --no-wiki    # videos only
scripts/publish-tours.sh v0.4.0 --wiki-only  # wiki pages only
```

GitHub creates the wiki repository when a person saves the first page. Before the first
run, open the Wiki tab of the repository and save any page. Nothing can push to a wiki
that has no page, and GitHub has no API for that step.

## How reproducible a build is

Measured on 2026-09-11 for both maps, with the same source files and the same lock file.

- The geometry is the same everywhere. Triangles, vertices, meshes, bounds, the origin
  height and the building count agree on macOS arm64, in the Docker container and on
  the Linux runner in CI.
- The file is not the same everywhere. The embedded JPEG differs between processor
  architectures, because the JPEG encoder in the Pillow wheel is built for the
  architecture. `tartu` is 20 bytes larger on the amd64 runner than on an arm64
  Mac, and every one of those bytes is in the image.
- macOS arm64 and the Docker container on the same Mac write a file that is equal byte
  for byte.

So a checksum of a `.glb` only proves that two builds ran on the same architecture. To
compare a build with a release, read `<name>-build-report.json` and compare the
geometry numbers and the source file names.

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
  terrain.py          height field to one grid mesh or a grid of chunks
  buildings.py        LOD2 OBJ to wall and roof meshes, grouped into chunks
  materials.py        template material names, JPEG and PNG textures
  probes.py           test objects near the spawn point
  export.py           named meshes to one glTF binary file
  inspect.py          statistics of a glTF binary file
  install.py          copy into the game folder
  build.py            the pipeline, step by step
  preview.py          the picture of a map from above
  tour.py             camera shots, camera math, the tour of a map
  render.py           offscreen OpenGL renderer, stills and video
  shots.py            in-game screenshots into the documentation
  gallery.py          the wiki pages: the index and one page per map
tests/                pytest, synthetic data, no network
docs/                 analysis, decisions, formats, licensing, locations, sources
data/                 downloaded geodata cache, not in git
dist/                 built maps and build reports, not in git
```

## Add a new map

1. Copy `maps/tartu-annelinn-test.toml` to `maps/<name>.toml`.
2. Set the name, the bounding box in L-EST97 or a WGS84 center with a size, and the
   municipalities that the box touches.
3. Run `uv run fpv-maps area maps/<name>.toml` and check the sheets and the chunks.
4. Build, install, fly.
5. Render the tour: `uv run fpv-maps tour maps/<name>.toml --publish`.
6. Add a row and a section to `docs/maps.md`, with two tour pictures.

For a map larger than about 4 km², copy `maps/tartu.toml` instead and keep three
settings from it:

- `ground_texture.source = "estonia"`, so that the download stays small.
- `chunks.size_m`, so that the engine can skip a mesh that the camera cannot see.
- A `terrain.step_m` of 8 to 12 m. A 2 m grid over 81 km² is 40 million triangles.

## Build a map from an own drone survey

The open data covers the whole country at one quality. A survey of one site gives far
more, over far less ground, and the pipeline reads three products of a
[DJI Terra](https://enterprise.dji.com/dji-terra) project: an elevation raster, an
orthophoto and the textured mesh as [3D Tiles](https://www.ogc.org/standards/3dtiles).
Install the extra once, because some tiles carry Draco compressed geometry:

```
uv sync --extra survey
```

A survey is not open data, so the pipeline never downloads it. A map names the files,
relative to the map file, and the build fails when one is missing rather than falling
back to the open data.

```toml
[drone]
elevation     = ["../survey/lidar/dem.tif"]   # terrain, bare earth is best
ortho         = ["../survey/ortho.tif"]       # replaces the open orthophoto where it reaches
mesh_tileset  = "../survey/terra_b3dms"       # the folder that holds tileset.json
mesh_elevation = ["../survey/photo/dsm.tif"]  # registers the mesh, see below
mesh_error_m   = 0.12                         # quality: meters of surface error
mesh_texture_px = 512                         # cap on the side of every tile texture
```

Three things decide whether the result lands where it should.

**Projection.** Terra writes UTM zone 35N and the pipeline works in L-EST97. Every
raster is warped on read, and the mesh comes through ECEF. Nothing to set.

**Height.** Terra writes ellipsoidal heights and the open data writes EH2000, about
19 m apart over Estonia. Worse, two flights over the same ground do not share a height
unless they shared an RTK base: the two flights over the test site stand 4.1 m apart
because each set its own base, three months apart. The build therefore measures every
survey against the open elevation model and shifts it into EH2000, which puts all of
them on each other. Name `mesh_elevation` whenever the mesh comes from a different
flight than `elevation`, so that the mesh is registered on its own.

**The double surface.** The terrain and the survey mesh describe the same ground twice,
and they disagree by centimeters, so the terrain pokes through the mesh at a grazing
angle. Set `terrain.sink_m = 0.5`. The origin is read before the sink, so the spawn
still stands on true ground and only the filler outside the mesh drops.

Use a bare earth model for `elevation`. A surface model holds the buildings, so the
terrain would carry them a second time under the mesh.

## Build a map with photo facades

Add a `[facades]` section to a map and the walls take their picture from the
Maa- ja Ruumiamet oblique photos instead of an in-game material. The roofs take the
orthophoto. `maps/tartu-old-town-facades.toml` is the worked example, and
`docs/facades.md` explains every step of the method.

```toml
[facades]
enabled = true
level = 12          # Deep Zoom level of the photo service. 13 is the full frame.
texel_m = 0.09      # how fine the atlas samples a wall
atlas_px = 16384    # atlas width. It grows in height until every panel fits.
max_candidates = 90 # photos to fit a camera to
max_sources = 22    # photos to bake from, spread over the compass
min_correlation = 0.30
jpeg_quality = 85
```

The first build is slow and the rest are not. The photo choice is cached as
`data/fotoladu/sources-<map>.json` and every Deep Zoom tile is cached under
`data/fotoladu/`, so a rebuild at another texel size costs no request. Delete the
sources file to choose the photos again.

Two things to know before you turn it on:

- **The map may not be published.** See `docs/licensing.md` D6. Set `private = true`
  in the `[map]` section, which is what keeps it out of the release and preview checks.
- **It needs `scipy`.** `uv sync --extra facades`.

## Add a gate course

A map that declares a `[course]` section gets a ring of gates, which makes a line
repeatable between two variants of a map. See `docs/benchmark.md` for the method.

```toml
[course]
height_m = 6.0        # defaults for every gate
size_m   = 6.0

[[course.gate]]
at = [657850.0, 6477950.0]   # L-EST97, east then north
height_m = 5.0               # over the terrain
yaw_deg  = 0.0               # 0 means a pilot flies through it heading north
```

The build counts the geometry inside every gate and in the approach to it, writes the
result into the build report, and warns when a gate is blocked. Check it after any
change to the geometry: a survey mesh changes shape with its quality setting, so a gate
that is clear in one variant can be blocked in another.

## Data budget

| Data set | Sheet | Size |
|----------|-------|------|
| DTM 1 m GeoTIFF | 5 x 5 km | 60 to 80 MB |
| City orthophoto 10 cm GeoTIFF | 1 x 1 km | 25 to 30 MB zipped |
| Estonia orthophoto 20 cm GeoTIFF | 5 x 5 km | about 185 MB zipped, 370 MB unpacked |
| Lidar, city flight, LAZ | 1 x 1 km | about 280 MB |
| LOD2 buildings OBJ, Tartu linn | whole city | 12 MB zipped, 64 MB unpacked |
| LOD2 buildings OBJ, Luunja vald | whole parish | 1.4 MB zipped |
| Trees LOD0 GPKG, Tartu linn | whole city | 39 MB zipped |

The whole city at 10 cm needs about 90 orthophoto sheets, 2.5 GB. The same area needs
only 6 sheets of the 20 cm product, so the base map sets `ground_texture.source` to
`estonia`. Keep `data/` on a fast disk.
