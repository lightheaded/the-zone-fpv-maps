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

Decision: `maps/tartu.toml` covers L-EST97 656000 to 665000 east and 6468500 to
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

Decision: the origin of `tartu` is 58.37990 north, 26.72743 east. That is mid
river, 134 m south east of the [Kaarsild](https://et.wikipedia.org/wiki/Kaarsild) and 188 m north west of the Võidu sild,
12 m from each bank, 31.4 m above sea level in EH2000.

Why: the center of the box is a field in Ropka. The game spawns the drone at the
origin, on the ground, with the camera to the north. Open water cannot hold a
building, so the drone can never spawn inside one, and the first view is the arch
bridge with [Toomemägi](https://et.wikipedia.org/wiki/Toomem%C3%A4gi) and the old town behind it. The point was found from the
elevation model and the orthophoto, not by eye: water is the flattest and darkest
part of the box.

## 2026-09-11: The first two detailed tiles are tartu-vaksali and tartu-ulejoe

Decision: the first two detailed maps are `tartu-vaksali`, the 1:2000 sheet 473658 in
the industry belt, and `tartu-ulejoe`, a 1 km² box over the [Emajõgi](https://et.wikipedia.org/wiki/Emaj%C3%B5gi) and
[Ülejõe](https://et.wikipedia.org/wiki/%C3%9Clej%C3%B5e). They come before
[Annelinn](https://et.wikipedia.org/wiki/Annelinn), which `docs/analysis.md` names first.

Why: the wall texture is the limit of the whole project, not the geometry. The open data
gives roofs at 10 cm and shapes at LOD2, and nothing open gives a facade. Own ground
photos are the only source with no permit and no size limit, and they need a landmark
that a person can walk around on public ground. Both tiles pass that test. The
[Aparaaditehas](https://aparaaditehas.ee/) courtyards are open to visitors, and the
veetorn, Pauluse kirik, the station, Lodjakoda, the stadium and the factory block at
Puiestee stand on public streets. A drone cannot replace the walk: a 907 g aircraft
without a class label flies A3 only, 150 m from a built up area.

The two tiles also carry the height that freestyle needs. Measured in the LOD2 data of
2026-09-05: `tartu-vaksali` holds 774 buildings with a median height of 6.2 m, 17 of
them over 20 m, a 49.0 m tower at the [Tartu Mill](https://tartumill.ee/) block and a
35.4 m water tower. `tartu-ulejoe` holds 882 buildings with a median height of 5.4 m, 10 of
them over 20 m, the 59.4 m spires of Peetri kirik, and two factory blocks of
107 x 80 m and 66 x 76 m.

Cost: neither tile is a whole cluster of `docs/locations.md`. `tartu-vaksali` is the
north half of cluster 4 and `tartu-ulejoe` is the south half of cluster 2. The rest of each
cluster waits for a later map.

## 2026-09-11: A detailed tile is 1 km² at 12 cm, even over four orthophoto sheets

Decision: a detailed tile is 1 x 1 km with an 8192 px ground texture. That is 12 cm per
pixel. `tartu-vaksali` aligns to the Maa-amet 1:2000 grid and needs one orthophoto
sheet. `tartu-ulejoe` does not align, and needs four.

Why: 12 cm is the finest ground texture that the memory budget in `docs/analysis.md`
allows. A 16384 px texture needs 1.4 GB of video memory instead of 0.36 GB. The
landmarks of Ülejõe span 802 x 675 m, and no sheet aligned box holds them all: a
2 x 1 km box puts the Kroonuaia sild 5 m from its edge, and a 2 x 2 km box costs the
same four sheets but drops the texture to 24 cm. Four downloads of 30 MB are cheaper
than the lost detail.

## 2026-09-11: The release page names new maps only, docs/maps.md is the inventory

Decision: `scripts/release-notes.sh` writes a section for each map that the release
adds, and names no other map. `docs/maps.md` lists every map with its area, its size
and its source data. The release assets stay complete: every map is in every release.

Why: a release page is a change list. A reader who opens v0.3.0 wants to know what is
new. A reader who wants the full list reads the repository, which is always current,
and a release page from four months ago is not. The assets stay complete because a
reader must never need to walk back through old releases to find one map file.

## 2026-09-11: The map tour is rendered from the glTF file, not captured in the game

Decision: `fpv-maps tour` renders the tour pictures and the tour video from
`dist/<name>/<name>.glb` with an offscreen OpenGL context. The pipeline never drives
the game. In-game screenshots stay a human step, and `fpv-maps shots` prepares them.

Why: the game cannot be automated. These facts come from the installed build of
2026-09-11, and `docs/the-zone-format.md` holds them in full:

- The game is a Godot 4.5.1 export. The engine accepts `--write-movie`, `--fixed-fps`
  and `--resolution`, so a frame locked capture is possible.
- The game has no free camera, no spectator, no replay and no photo mode.
- The game reads a gamepad as an RC radio. A flight comes from stick input.
- No command line option loads a map. A capture must navigate the menu.

So an automated in-game tour needs synthetic input for the menu and for the flight.
That breaks with every game update, it needs an accessibility permission on macOS, and
Movie Maker mode separates the game clock from the wall clock, so the same input gives
a different flight every run. A build agent can never run it: the game is proprietary,
it is 10.5 GB and it needs Steam and a GPU.

The renderer reads the file that the game loads, so the geometry, the ground texture
and the spawn point are the true ones. It runs on macOS, Windows and Linux, it needs no
game, and it renders 1920 x 1080 at 44 to 71 frames per second on a workstation GPU.

Cost: the picture is not the picture of the game. There is no shadow, no vegetation and
no in-game material, and a wall carries the fallback color of the material name. The
tour therefore shows the shape of a map, not the look of a flight. That is what the
inventory needs. A person who wants the look of the game adds in-game screenshots.

The renderer is an optional extra of the package, `uv sync --extra tour`. glcontext,
which moderngl needs, ships source only for Linux and Windows, so a required dependency
would force a C++ compiler on every contributor and on every CI job. The pipeline
itself installs from wheels alone, and it stays that way.

Not chosen: a photoreal render with Blender Cycles. It looks better and it costs hours
per map, a heavy dependency and a second material system.

Note on the sun: the orthophoto carries the shadows of the flight of 2024-04-27, with
the sun in the south. The renderer puts its sun in the south too and casts no shadow of
its own, so the two never disagree.

## 2026-09-11: Tour videos live in the release, the wiki holds the gallery

Decision: `docs/maps.md` stays the inventory and shows two tour pictures per map. Every
tour picture goes into `docs/screenshots/`. The tour video goes to the release as an
asset, never into git. `fpv-maps gallery` writes the wiki: an index page, one page per
map, a sidebar and a footer. Every picture is linked from the repository and every video
from the newest release.
`scripts/publish-tours.sh` uploads the videos and pushes the page.

Why: a tour video is 30 to 100 MB. Git keeps every version of it forever, and a
collaborator who clones the pipeline does not want them. A release asset costs nothing
in the clone and it is versioned with the map file that it shows. The wiki is a
separate repository, so a long gallery page does not add noise to a pull request. The
pictures are linked, not copied, so the wiki never holds a second copy that ages.

Cost: the wiki pages are generated, so nobody must edit them by hand. A map that changes
needs `scripts/publish-tours.sh` again. GitHub does not play an MP4 asset in the page,
so the link starts a download.

## 2026-09-11: Every map name starts with its city

Decision: a map name is `<city>` for the map of a whole city, and `<city>-<place>` for
a tile in it. The four maps of Tartu are `tartu`, `tartu-vaksali`, `tartu-ulejoe` and
`tartu-annelinn-test`. The name stays letters, digits, `-` and `_`, because the game
uses it as a folder name and a file name.

Why: the project starts with one city and does not end there. A name like `vaksali`
says nothing to a person who does not know Tartu, and a second city with a district of
the same name breaks the namespace. The custom map browser of the game is one flat
list for everybody, so a name must carry its place. `tartu` is short for the map of the
whole city, because the city name alone is the clearest name for it.

Cost: every file name changed. `docs/screenshots/` and the map files in the release of
version 0.4.0 carry the new names. The releases v0.1.0 to v0.3.0 keep the old names,
because a published asset must never change under a reader. A person who installed
`vaksali` must install `tartu-vaksali` and delete the old folder.

## 2026-09-12: A survey mesh is chosen by geometric error, not by tile level

Decision: a map asks for a quality in meters of surface error, `drone.mesh_error_m`,
and the build walks the 3D Tiles tree and stops at the first node good enough. It does
not take one level of the pyramid.

Why: a level is not a quality. The pyramid of the test site runs from level 14 to level
25, and the deep levels are sparse: level 25 holds nine tiles, because the tree only
goes deeper where the reconstruction found more detail. Taking one level therefore
leaves holes. Geometric error is also a physical quantity, so the same number means the
same thing on another survey with another tree, and it is the number a reader of a
benchmark can compare against a screen resolution and a flying speed.

Cost: the walk has to follow a JSON file per node, because Terra links children through
sub tileset files rather than inline.

## 2026-09-12: Every survey is registered against the open elevation model

Decision: the build measures the height offset of each survey raster against the
Maa-amet 1 m model over the map box and shifts the survey into EH2000. A map names
`drone.mesh_elevation` when the mesh comes from a different flight than the terrain, so
that the mesh is registered on its own.

Why: [DJI Terra](https://enterprise.dji.com/dji-terra) writes ellipsoidal heights, about 19 m above EH2000 over Estonia.
That alone would be a fixed geoid correction. But the two flights over the test site
also stand 4.1 m apart from each other, because each set its own RTK base three months
apart, and no geoid model knows that. Measuring each flight against one common model
fixes both faults at once and needs no extra file. Without it the photogrammetry mesh
floated 4 m over its own terrain, which is how the fault was found.

The estimator is the peak of the height difference, not its mean or its median. A
surface model holds roofs and trees, which are real and only ever positive, so they
pull a mean and a median up. They do not move the peak, because open ground is the most
common surface of a suburban scene.

## 2026-09-12: The filler terrain sinks under a survey mesh

Decision: a map with a survey mesh sets `terrain.sink_m`, and the build lowers the
terrain by it. The origin is read before the sink.

Why: the terrain and the mesh describe the same ground twice and disagree by a few
centimeters, so about seven percent of the mesh ground fell below the terrain and the
terrain showed through the photogrammetry at a grazing angle. Half a meter is enough to
separate them, and it is invisible outside the mesh, where the terrain is the only
ground. Reading the origin first keeps the spawn on true ground.

## 2026-09-12: Draco decoding is an optional extra, like the tour renderer

Decision: `uv sync --extra survey` installs [DracoPy](https://github.com/seung-lab/DracoPy). The base install does not.

Why: Terra compresses part of a pyramid with `KHR_draco_mesh_compression` and leaves
the rest plain, so a reader of a survey has to do both. No map in `maps/` reads a
survey, so the dependency has no place in the base install. DracoPy ships wheels for
macOS, Windows and Linux, so the extra still needs no compiler, unlike `tour`.

## 2026-09-12: Private map configs live in maps-private, which git ignores

Decision: a map that reads data nobody published lives in `maps-private/`, not in
`maps/`. The folder is in `.gitignore`. The pipeline, the documentation and the
measured numbers stay public.

Why: the release workflow builds every map in `maps/` from the open data and publishes
it. A map that reads a private survey would fail that build, and if it did not fail it
would publish the survey. Keeping the two folders apart makes the rule structural
rather than a thing to remember. `maps-private/generate.py` writes a family of variants
from one specification, so that everything the variants must share really is shared.

## 2026-09-12: A benchmark map carries its own gate course

Decision: a map may declare a `[course]` section, and the build puts a ring of gates in
it and checks that every gate is flyable.

Why: the game has no free camera, no replay, no telemetry export and no command line
option that loads a map, so a frame rate comes from a person flying a line. Two such
numbers are only comparable when the line is the same, and the only way to hold a line
fixed across map files is to draw it into them. A gate is four thin boxes, 48 triangles
and one flat color, which is far below the noise of the thing being measured.

The build checks the gates because a survey mesh changes shape with its quality
setting: a gate that is clear at 25 cm of error can be blocked at 3 cm. The first
placement of gate 6 stood inside a treeline, which the check found.
