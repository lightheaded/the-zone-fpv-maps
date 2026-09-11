# Decision log

One entry per decision that the code does not explain by itself. Newest last. License
decisions D1 to D6 are in `docs/licensing.md`.

## 2026-09-11: Python with uv, not Blender, for the automated pipeline

Decision: the pipeline is a Python package. [uv](https://docs.astral.sh/uv/) manages the interpreter, the
dependencies and the lock file. Blender is an authoring tool for hero assets only.

Why: Blender containers exist for Linux x86_64 only, and the Blender Python API changes
between versions. The Python geodata wheels (rasterio, pyproj, pyogrio, shapely) bundle
GDAL and PROJ, so the same lock file installs on macOS arm64, Windows x64 and Linux.
[trimesh](https://trimesh.org/) writes glTF binary files with named nodes, named materials and embedded JPEG
or PNG textures, which is all the game needs.

## 2026-09-11: Two ways to run, native and Docker, same lock file

Decision: `uv run fpv-maps ...` for daily work on macOS and Windows. `docker compose
run pipeline ...` for a reproducible build and for CI. Both install from `uv.lock`.

Why: native runs are faster to iterate and can copy the result into the game folder.
Docker gives a collaborator a build that works on the first try. The image is
`python:3.12-slim` plus the locked wheels. It runs native on amd64 and arm64.

## 2026-09-11: CI runs on Linux, macOS and Windows

Decision: the [GitHub Actions](https://github.com/features/actions) matrix installs and tests on all three, and builds the
Docker image.

Why: the maintainer works on macOS and Windows. A path or line ending bug must fail in
CI, not on the second machine. `.gitattributes` forces LF line endings.

## 2026-09-11: One TOML file per map, the map name is the game folder name

Decision: `maps/<name>.toml` holds the area, the quality settings and the layers.
`dist/<name>/<name>.glb` is the output. The name allows letters, digits, `-` and `_`.

Why: the game requires that the folder name and the file name are equal. A config file
per map makes every map reproducible and reviewable in a pull request.

## 2026-09-11: Coordinates in (east, north), game axes X east, Y up, Z south

Decision: all code orders L-EST97 coordinates as (east, north). `crs.py` is the only
module that converts to game axes. The map origin is the spawn point and sits on the
terrain surface.

Why: EPSG:3301 has the axis order north, east in its official definition, which
confuses libraries. One explicit order avoids swapped coordinates. A right handed
Y up system with Z south keeps the map readable from above: X to the right, north up.

## 2026-09-11: The test tile aligns with Maa-amet sheet 473662

Decision: the first test tile is the 1:2000 sheet `473662`, 1 x 1 km in Annelinn.

Why: one orthophoto sheet and one lidar sheet cover it. The sheet holds panel houses,
the ring road, and the west end of Lohkva, so it tests two municipalities at once.

## 2026-09-11: Buildings per municipality, not per bounding box

Decision: the config lists the Maa-amet municipality files to load, for example
`["Tartu_linn", "Luunja_vald"]`. The pipeline keeps the buildings inside the box. There is
no default. A map with buildings must name its municipalities.

Why: Maa-amet publishes LOD2 buildings per municipality. Lohkva is in Luunja vald,
so an Annelinn map that stops at the city border loses half of its east side.

## 2026-09-11: Probes in the test tile instead of questions on Discord only

Decision: the test tile carries small test objects near the spawn point, one per open
question about the game. `docs/the-zone-format.md` lists them.

Why: an answer from a flight is a verified fact. A Discord answer is a hint. Both help.

## 2026-09-11: CI builds the release assets from the map configs

Decision: a tag `vX.Y.Z` makes GitHub Actions build every map in `maps/` from the
open data and publish the files. One version for the whole repository. Release notes
come from commit messages, as in the maintainer's other projects. Previews and
in-game screenshots live in `docs/screenshots/` so that a person can see a map
before the install.

Why: a map built in CI is reproducible from the config and the data date. A map built
on a laptop is not. The commit history already explains every change, so the release
page reads it instead of a second text that nobody writes.
