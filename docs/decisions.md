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

## 2026-09-11: Large maps use the 20 cm Estonia orthophoto, small maps the 10 cm city one

Decision: `ground_texture.source` picks the product. `city` is the 10 cm orthophoto on
1 x 1 km sheets. `estonia` is the 20 cm orthophoto on 5 x 5 km sheets. The base map
uses `estonia`.

Why: the base map box needs 90 city sheets, about 2.5 GB, but only 6 Estonia sheets,
1.1 GB. The ground texture of the base map is 1.1 m per pixel, so the extra detail of
the 10 cm product is thrown away in the same step. A 1 km² tile keeps `city`.

## 2026-09-11: A large map is a grid of chunks, not one mesh

Decision: `chunks.size_m` splits the terrain and the buildings into square cells. The
base map uses 1500 m, which gives 36 terrain meshes and 72 building meshes. A map
without the setting stays one terrain mesh, as before.

Why: a game engine draws a mesh only when the camera can see it. One 81 km² mesh is
always drawn in full. The chunks share the lattice of the whole map, so two neighbors
have equal edge vertices and no crack appears. Every chunk points at the same material
object, so the file still holds one ground image and three materials.

## 2026-09-11: The elevation model is read at half the terrain step

Decision: `dtm_resolution` reads the 1 m elevation model at `step / 2`, never finer
than the data. The base map reads at 5 m for a 10 m terrain.

Why: 81 km² at 1 m is 81 million cells and 648 MB in memory, and a 10 m mesh cannot
show that detail. The Maa-amet sheets are averaged while they are read, and the test
`test_read_heights_does_not_average_nodata_into_the_terrain` shows that a data hole
does not pull the terrain down.

## 2026-09-11: The base map is a 9 x 9 km square, not the whole city municipality

Decision: `maps/tartu-base.toml` covers L-EST97 656000 to 665000 east and 6468500 to
6477500 north. That is 81 km². It holds every cluster in `docs/locations.md` except
[Tartu lennujaam](https://www.tartu-airport.ee/), which is 6 km further south.

Why: the city of Tartu took in Tähtvere vald in 2017, so the municipality reaches
14 km west to Ilmatsalu and Rahinge. Those are fields and villages. A square box over
the built city gives more flying value per megabyte. The box edges fall on the
Maa-amet 1:10000 grid, so 6 elevation sheets and 6 orthophoto sheets cover it.

Cost: 2282 of the 22468 city buildings fall outside, 2254 of them west and 504 north.
Five municipalities meet inside the box and all five are in the config. Nõo vald
touches the corner but has no building inside, so it is not in the list.

## 2026-09-11: The base map spawns on the Emajõgi, not at the center of the box

Decision: the origin of `tartu-base` is 58.37990 north, 26.72743 east. That is mid
river, 134 m south east of the [Kaarsild](https://et.wikipedia.org/wiki/Kaarsild) and 188 m north west of the Võidu sild,
12 m from each bank, 31.4 m above sea level in EH2000.

Why: the center of the box is a field in Ropka. The game spawns the drone at the
origin, on the ground, with the camera to the north. Open water cannot hold a
building, so the drone can never spawn inside one, and the first view is the arch
bridge with [Toomemägi](https://et.wikipedia.org/wiki/Toomem%C3%A4gi) and the old town behind it. The point was found from the
elevation model and the orthophoto, not by eye: water is the flattest and darkest
part of the box.
