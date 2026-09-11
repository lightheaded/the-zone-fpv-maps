# What The Zone loads: verified facts and open questions

Date: 2026-09-11. Facts come from the game folder of the macOS Steam install, the
[custom maps wiki page](https://wiki.thezonefpv.com/custom_maps.html), and the first
test tile. The Blender template and the official maps are proprietary. This document
records facts about them, not their content.

## Game folder

```
<game folder>/
  custom_map_blender_template/template.blend   52 MB, Blender template
  custom_maps/<name>/<name>.glb                 custom maps, folder name = file name
  maps2/maps/<id>/map.glb                       official maps
  maps2/maps/<id>/manifest.json                 spawn point, skybox, placed assets
  maps2/maps/<id>/occluder.occ                  occlusion culling data
  maps2/maps/<id>/baked_<lighting>_<quality>/   baked lightmaps as DDS, per quality level
```

On macOS the game folder is `$HOME/Library/Application Support/Steam/steamapps/common/The Zone FPV`.
On Windows it is `C:\Program Files (x86)\Steam\steamapps\common\The Zone FPV` by default.
The pipeline reads the environment variable `THE_ZONE_DIR` first.

## The game engine

Read from the installed build of 2026-09-11. The facts matter for automation: they say
what a script can drive and what needs a person. See `docs/decisions.md`.

- The game is an export of [Godot](https://godotengine.org/) 4.5.1 stable. The macOS bundle holds one
  executable of 188 MB and one package file of 10.5 GB. It links the Steam addon.
- The engine accepts the standard Godot options, among them `--write-movie`,
  `--fixed-fps`, `--resolution`, `--quit-after`, `--fullscreen` and `--headless`.
  Movie Maker mode therefore works, and it writes frame locked video.
- The game reads a gamepad as an RC radio. The settings file holds a channel map, a
  rate profile per axis and a keybind list. A flight comes from stick input.
- The package holds a custom map editor, a map browser, an upload step and a download
  step. It holds no free camera, no spectator, no replay and no photo mode.
- No command line option loads a map. A capture must navigate the menu.

The user settings live at `Godot/app_userdata/The Zone/settings.cfg` in the
application data folder of the operating system. The game writes a log beside it.

## Official maps as a size reference

Read with `fpv-maps inspect` from the three official map files. All three were
exported from [Blender](https://www.blender.org/) with the Khronos glTF exporter.

| Map | File size | Triangles | Meshes | Materials | Extent | Embedded images |
|-----|-----------|-----------|--------|-----------|--------|-----------------|
| 1 | 148 MB | 1.79 M | 1295 | 1017 | 1000 x 1000 m | none || shown, first flight 2026-09-11 |
| 2 | 110 MB | 1.33 M | 1715 | 919 | about 200 x 1000 m, 1000 m tall | none || shown |
| plaza | 76 MB | 0.98 M | 2831 | 3340 | about 1400 x 1000 m | 7 PNG, 6.7 MB |

Our own maps, for the same comparison:

| Map | File size | Triangles | Meshes | Materials | Extent | Embedded images |
|-----|-----------|-----------|--------|-----------|--------|-----------------|
| tartu-annelinn-test | 23 MB | 0.51 M | 14 | 10 | 1000 x 1000 m | 1 JPEG, 1 PNG, 11.3 MB |
| tartu | 126 MB | 2.87 M | 108 | 3 | 9000 x 9000 m | 1 JPEG, 18.9 MB |
| tartu-vaksali | 26.5 MB | 0.55 M | 3 | 3 | 1000 x 1000 m | 1 JPEG, 12.2 MB |
| tartu-ulejoe | 25.8 MB | 0.54 M | 3 | 3 | 1000 x 1000 m | 1 JPEG, 11.6 MB |

Every map of the table loads in the game. `tartu-vaksali` and `tartu-ulejoe` were loaded on
2026-09-11 and neither crashed the game. No other property of them is measured yet.

Conclusions:

- A 1 km² tile with 0.5 to 2 million triangles is inside the range that the game
  ships. A detailed tile of 1 km² holds about 0.55 million triangles and 26 MB, of
  which the ground texture is 12 MB. Three meshes carry it: terrain, walls and roofs. The base map of the whole city is 126 MB and 2.87 million triangles, which
  is 1.6 times the triangles of the largest official map and 0.85 times its file
  size. Test it before you rely on it.
- One official map embeds PNG textures. This suggests that embedded textures work.
- Official map 1 uses the [Godot](https://godotengine.org/) name suffix `-col` on 917 nodes. Official maps go
  through the Godot editor import, which honors the suffix. Whether the runtime loader
  for custom maps honors it is open. Probe 5 tests it.
- The official maps have lightmaps and occluders that a custom map cannot provide.
  Expect flat lighting in custom maps.

## The Blender template

- 13 mesh objects and 382 materials. All material names start with `z_`. The game
  replaces a material by name with its own texture at load time. The full list is in
  `docs/the-zone-materials.md`. The pipeline uses these names for walls and roofs so
  that the buildings match the look of the official maps.
- The template has no spawn object, no gate object and no special object names. The
  ground is a box of 666 x 532 m with its top face at Z = -1.07 m in Blender. This
  suggests that the game spawns near the origin, above the ground. The pipeline puts
  the map origin on the terrain surface, so that Y = 0 is the ground at the spawn.
- glTF export settings stored in the template: apply modifiers on, renderable objects
  only. The Blender exporter writes Y up, which is the glTF standard. The pipeline
  writes Y up directly.
- Scale is 1 unit = 1 m.

## Manifest of official maps

`manifest.json` has the keys `spawn_point` (9 numbers: position, rotation, scale),
`skybox`, `lighting_variations` and `assets` (placed props with a `custom_type` such
as `spray_can`). Custom maps have no manifest on the wiki. Whether the game reads one
from `custom_maps/<name>/` is open. Do not build on it.

## Open questions and the probes that answer them

The test tile `maps/tartu-annelinn-test.toml` places these objects near the spawn point.
Fly to each one and record the answer in the table.

| # | Question | Probe | Where | Answer |
|---|----------|-------|-------|--------|
| 1 | Does the game show a large JPEG texture embedded in the file? | `terrain`, 8192 px orthophoto | everywhere | shown, first flight 2026-09-11 |
| 2 | Does the game show a small PNG texture embedded in the file? | `probe_texture_box`, orange checker | 12 m east, 14 m north | shown |
| 3 | Does a material with an unknown name keep its color? | `probe_color_box`, red | 12 m east, 8 m north | shown, but pink. The pipeline wrote sRGB into a linear field. Fixed before v0.1.0 |
| 4 | Does a template material name get the in-game texture? | `probe_template_box`, `z_rough-brick1`; all building walls and roofs | 12 m east, 20 m north | yes, walls and roofs get the in-game concrete and asphalt textures |
| 5 | Does a thin wire collide? | `probe_wire`, 2 cm thick, 7.5 m high | 25 m south, between two poles | open |
| 6 | Does the runtime honor the `-col` suffix (invisible but solid)? | `probe_wire-col`, 6.5 m high | below probe 5 | open |
| 7 | Where does the game spawn, and in which direction? | `probe_spawn_pad`, yellow disc at the origin | origin | at the origin, on the ground, camera faces north |
| 8 | Do LOD2 buildings collide? | any panel house | everywhere | open |
| 9 | Is there a world boundary? | fly 500 m to the edge | edge | open |
| 10 | Load time of a 23 MB file? | | | a few seconds, 170 FPS on the Mac |

The base map `tartu` asks four more questions. There are no probe objects in it,
so fly it and record the answers here.

| # | Question | How to test | Answer |
|---|----------|-------------|--------|
| 11 | Does the game load a 126 MB file, and how long does it take? | start the map with a stop watch | the map loads on the Mac, first test 2026-09-11. The load time is not measured yet |
| 12 | Does the frame rate hold with 108 meshes over 81 km²? | fly a straight line across the map | open |
| 13 | Does the game keep position accuracy 4.5 km from the origin? | fly to a corner and hover | open |
| 14 | Do the terrain chunks show a seam or a crack? | fly low over a chunk border, 1500 m grid from the spawn | open |

Also record: frame rate on both machines, and whether the terrain has visible steps
at the 2 m grid.

## Known gaps of the base map

- The ground texture is 1.1 m per pixel. Roads and roofs read from 100 m up, and
  single cars do not.
- The terrain grid is 10 m. The bank of the Emajõgi and the slope of Toomemägi lose
  their edge. A detailed map of the same place uses 2 m.
- There is no water surface. The elevation model gives the water level of the flight
  day, so the river is a flat strip of terrain, and the drone lands on it.
- Walls and roofs use two in-game materials for all 23745 buildings. Every house in
  the city has the same concrete wall and the same asphalt roof.
- Trees, power lines, towers, bridges and fences are not in it. The bridges of the
  Emajõgi are gaps in the terrain texture with nothing above them.
- Buildings whose center lies outside the box are dropped, as in the test tile.

## Known gaps of the test tile

- Buildings whose center lies outside the box are dropped. A building that the box
  edge cuts is either whole or absent. Fix: include every building that intersects
  the box, or clip it.
- Greenhouses are not in the LOD2 buildings data. Maa-amet has a separate LOD1 data
  set for roofed structures and greenhouses.
- Trees, roads, water and power lines are not in the test tile.
- Walls and roofs have world space UVs with one texture repeat per 4 m. The right
  scale for the in-game textures is open.
