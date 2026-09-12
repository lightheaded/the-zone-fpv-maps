# Benchmarking a map: a fixed course and a family of variants

Date: 2026-09-12. Status: the maps are built and the first flights are flown.

`docs/analysis.md` estimates what The Zone can carry. This document measures it. The
estimates there come from the file sizes of the official maps and from a worst case
guess at the texture memory. Neither says where the game actually slows down, and
nobody has published a city scale or a photogrammetry map, so there is no prior art.

The method is one course flown on several variants of one map. Every variant changes
one thing. The frame rate difference between two variants is then the price of that
one thing, on that one machine.

## Why a course

The game has no free camera, no replay, no telemetry export and no command line option
that loads a map. A frame rate is therefore read by a person, from a flight that a
person flew. Two such flights are only comparable when they follow the same line.

So the line is built into the map. Six gates stand at fixed points, in a fixed order,
the same in every variant. The pilot spawns at gate 1, flies 1 to 6 and back through
gate 1, and reads the frame rate. The gates are four thin boxes each, 48 triangles, one
flat color and no texture, so the course itself never moves the number it measures.

The build checks that the course is flyable. `check_clearance` counts the geometry
inside every gate and in the approach to it, and the build report holds the result.
This is not a formality: the first placement put gate 6 inside a treeline, and a survey
mesh changes shape with the quality setting, so a gate that is clear in one variant can
be blocked in another.

## What the family isolates

Two sources, two families, one origin and one course.

**The photogrammetry family** is a 200 m box over a site flown with a
[DJI](https://www.dji.com/) Zenmuse P1 at
50 m, the gimbal at 45 degrees for the whole flight. The reconstruction is a textured
mesh, delivered as [3D Tiles](https://www.ogc.org/standards/3dtiles). A 3D Tiles pyramid refines by geometric error, in
meters of surface error, which is a better quality knob than a polygon count because it
is a physical quantity. The family walks it from 25 cm to 3 cm.

**The lidar family** is a 640 m box over the same ground, from a Zenmuse L2 flight. It
has no mesh and no orthophoto of its own, so the terrain comes from the 9.8 cm lidar
elevation model, the buildings from the open LOD2 model and the ground texture from the
open 10 cm orthophoto. The family walks the terrain step from 2 m to 0.5 m.

The pair `vahi-molla-fine` and `vahi-molla-fine-flat` is the important one. They hold
the same geometry and differ only in the texture, by a factor of eight. If the frame
rate moves between them, texture memory is the limit. If it does not, triangles are.
Nothing else in the family separates those two.

## The surveys are not published

The maps read an own drone survey of a private site. The survey is not in this
repository, it is not in a release, and the map files are not published anywhere. What
is published is the pipeline that reads such a survey, and the numbers in the table
below. `maps-private/` holds the map configuration and git ignores it.

Anyone with their own survey can reproduce the family. `docs/development.md` has the
shape of the `[drone]` and `[course]` sections.

## How to run it

1. Build the family and install one variant:
   `uv run fpv-maps build maps-private/<name>.toml --install`.
2. Start the game, Play Offline, pick the map.
3. Fly the course three times. Discard the first lap, which loads textures.
4. Record the frame rate, the resolution, the quality preset and the machine.
5. Record the load time from picking the map to the spawn.
6. Note anything else: stutter at a gate, a texture that arrives late, a fall through
   the ground, a building with a wrong shape.

Repeat on both machines. Fill the table with `uv run fpv-maps benchmark --out
docs/benchmark-table.md`, which writes the cost half, and add the frame rates by hand.

Name the machines in the report. A frame rate without a GPU, a resolution and a
quality preset beside it is not a measurement. The two columns of the table below are
one laptop and one desktop with a recent 32 GB card, which is close to the ceiling of
what a player has, so a variant that does not hold up there will not hold up anywhere.

## What a map costs

Written by `fpv-maps benchmark`. The texture memory is the worst case of a runtime
glTF loader: four bytes per pixel plus one third for the mip chain, nothing compressed
on the GPU. The tile texture column is a cap, so a tile that was already smaller counts
too high and the memory column is an upper bound.

| Map | Box | Mesh error | Tile texture | Terrain | Ground px | Triangles | Meshes | Images | File | Texture VRAM | FPS desktop |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `tartu-vaksali` | 1000 m | - | - | 2.00 m | 12.2 cm | 551,969 | 3 | 1 | 26 MB | 0.25 GB | 1005 |
| `vahi-molla-lite` | 200 m | 0.25 m | 256 px | 1.00 m | 4.9 cm | 563,913 | 165 | 126 | 29 MB | 0.12 GB | |
| `vahi-molla` | 200 m | 0.12 m | 512 px | 0.50 m | 2.4 cm | 1,293,119 | 269 | 230 | 63 MB | 0.63 GB | 696 |
| `vahi-molla-fine` | 200 m | 0.06 m | 1024 px | 0.50 m | 2.4 cm | 2,282,712 | 421 | 382 | 109 MB | 2.32 GB | 663 |
| `vahi-molla-fine-flat` | 200 m | 0.06 m | 256 px | 0.50 m | 2.4 cm | 2,282,712 | 421 | 382 | 91 MB | 0.46 GB | 577 |
| `vahi-molla-max-8k` | 200 m | 0.03 m | 1024 px | 0.25 m | 2.4 cm | 5,215,426 | 723 | 684 | 222 MB | 1.83 GB | 427 |
| `vahi-molla-max` | 200 m | 0.03 m | 1024 px | 0.25 m | 1.2 cm | 5,215,426 | 723 | 684 | 251 MB | 4.89 GB | 450 |
| `vahi-molla-wide-lite` | 640 m | - | - | 2.00 m | 15.6 cm | 206,390 | 116 | 1 | 5 MB | 0.08 GB | |
| `vahi-molla-wide` | 640 m | - | - | 1.00 m | 7.8 cm | 820,790 | 116 | 1 | 19 MB | 0.33 GB | |
| `vahi-molla-wide-max` | 640 m | - | - | 0.50 m | 7.8 cm | 3,278,390 | 116 | 1 | 44 MB | 0.33 GB | |

Flown 2026-09-12 on a desktop with an [RTX 5090](https://www.nvidia.com/en-eu/geforce/graphics-cards/50-series/rtx-5090/) at 3840 x 1600, one reading per map
from the frame counter of the game. The laptop column is still open.

For scale, from `docs/the-zone-format.md`: the three official maps hold 0.98, 1.33 and
1.79 million triangles in 76 to 148 MB, and the `tartu` base map holds 2.87 million in
126 MB over 81 km².

## What the first flights answered

Three of the four questions are answered, on one machine.

**A 16384 px embedded texture loads and works.** `vahi-molla-max` carries one and ran
at 450 FPS. It was also the best looking map of the set. The estimate in
`docs/analysis.md` that the Godot limit is usable holds.

**Texture memory is not the binding constraint, and the pair that was built to test it
says so clearly.** `vahi-molla-fine` and `vahi-molla-fine-flat` hold the same 2.28
million triangles and differ only in texture, 2.32 GB against 0.46 GB. The map with
five times the texture ran *faster*, 663 against 577. A texture cut cannot make a map
slower, so the 86 FPS between them is where the camera was pointing, not the texture.
Any real cost of texture memory is under that noise on a 32 GB card. The same holds
for `vahi-molla-max` against `vahi-molla-max-8k`: 450 against 427, with the larger
texture again ahead.

**Triangles cost something, and the budget is far larger than this project assumed.**
551,969 triangles gave 1005 FPS, 1.29 million gave 696, 2.28 million gave 663 and 5.22
million gave 450. Every one of these maps draws with no lightmap and no occluder,
because the game builds neither for a custom map. A 5.22 million triangle map, which is
1.8 times the largest map this project has published and 2.9 times the largest official
map, still ran at three times a 144 Hz panel.

So the honest headline for the developers is that neither limit named in
`docs/analysis.md` was reached. What was reached was a correctness limit in this
pipeline, not in the engine: every map before 2026-09-12 shipped with its textures
mirrored top to bottom, and the flights above are the first that show what the data
actually looks like.

**Load time is still open.** Nobody timed it, and it is the one number a 251 MB map
makes people ask about.

### How to read these numbers

One instantaneous reading per map, from six separate flights, each with the camera
wherever the pilot happened to be. That is enough to say a map runs at 450 FPS rather
than 45, and enough to rule out a limit that was expected to be dramatic. It is not
enough to rank two maps that are 15 percent apart. A ranking needs the lap flown three
times per map with the reading taken at the same gate, which is what the course is for.
