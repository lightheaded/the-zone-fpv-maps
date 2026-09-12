# Benchmarking a map: a fixed course and a family of variants

Date: 2026-09-12. Status: the maps are built and the flights are open.

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

| Map | Box | Mesh error | Tile texture | Terrain | Ground px | Triangles | Meshes | Images | File | Texture VRAM | FPS laptop | FPS desktop |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `vahi-molla-lite` | 200 m | 0.25 m | 256 px | 1.00 m | 4.9 cm | 563,913 | 165 | 126 | 29 MB | 0.12 GB | | |
| `vahi-molla` | 200 m | 0.12 m | 512 px | 0.50 m | 2.4 cm | 1,293,119 | 269 | 230 | 63 MB | 0.63 GB | | |
| `vahi-molla-fine` | 200 m | 0.06 m | 1024 px | 0.50 m | 2.4 cm | 2,282,712 | 421 | 382 | 109 MB | 2.32 GB | | |
| `vahi-molla-fine-flat` | 200 m | 0.06 m | 256 px | 0.50 m | 2.4 cm | 2,282,712 | 421 | 382 | 91 MB | 0.46 GB | | |
| `vahi-molla-max` | 200 m | 0.03 m | 1024 px | 0.25 m | 1.2 cm | 5,215,426 | 723 | 684 | 251 MB | 4.89 GB | | |
| `vahi-molla-wide-lite` | 640 m | - | - | 2.00 m | 15.6 cm | 206,390 | 116 | 1 | 5 MB | 0.08 GB | | |
| `vahi-molla-wide` | 640 m | - | - | 1.00 m | 7.8 cm | 820,790 | 116 | 1 | 19 MB | 0.33 GB | | |
| `vahi-molla-wide-max` | 640 m | - | - | 0.50 m | 7.8 cm | 3,278,390 | 116 | 1 | 44 MB | 0.33 GB | | |

For scale, from `docs/the-zone-format.md`: the three official maps hold 0.98, 1.33 and
1.79 million triangles in 76 to 148 MB, and the `tartu` base map holds 2.87 million in
126 MB over 81 km².

## What to report

The useful report to the developers is not "it runs" or "it does not". It is the point
where the curve bends, with the cost table beside it. Four questions are open, and the
family answers them:

1. At which triangle count does the frame rate leave the refresh rate, on each machine?
2. Does texture memory or triangle count bind first? The `fine` and `fine-flat` pair
   answers this alone.
3. Does a 16384 px embedded texture load at all? `vahi-molla-max` carries one, which is
   the Godot limit. If it fails, the limit for a custom map is lower than the engine's.
4. How does load time grow with file size, from 29 MB to the largest variant?

Two facts that the answers need in order to be read properly. A custom map gets no
lightmap and no occluder, because the game builds neither at load time, so every one of
these maps draws without occlusion culling. And a photogrammetry mesh is many meshes
with one texture each, which is a different shape of load from a hand built map with
few meshes and many materials, so the mesh count column matters as much as the
triangles.
