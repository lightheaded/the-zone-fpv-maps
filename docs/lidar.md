# A map built from the laser scan itself

Date: 2026-09-13. Status: the pipeline builds one. `suburb-1-scan` is the first.

Every other map in this repository builds its world from two derived products: the
digital terrain model for the ground and the LOD2 vector model for the houses. Both
are interpretations of an earlier measurement, and both throw away most of what was
measured.

- The terrain model is bare earth. The trees, the buildings and everything else that
  stands on the ground have been removed from it on purpose.
- An LOD2 building is a box with a roof shape fitted to it. It has no chimney, no
  balcony, no porch and no greenhouse, and a building that is not box shaped is a
  box anyway.
- Nothing carries a tree, a fence, a mast, a power line or a pile of gravel.

So a map of the two is a village of boxes on a lawn. The laser scan those products
come from holds all of it.

## What the scan is

[Maa- ja Ruumiamet](https://geoportaal.maaruum.ee/) publishes the aerial lidar as LAZ, on 1 x 1 km sheets. Over Tartu
the 2024 flight measured 23 to 29 points per square metre, which is one point about
every 20 cm. Every point carries a height, a classification, an intensity, a near
infrared value and a red, green and blue value.

The colour matters as much as the geometry. A point cloud with colour needs no
orthophoto: the map can be textured from the measurement that made it.

## What the pipeline does with it

`[lidar] enabled = true` replaces the terrain model with the scan.

1. **Grid the points.** The highest return in each cell of `res_m` becomes the
   height of that cell, and its colour becomes the colour of that cell. This is the
   surface a drone would hit. Classes 7 and 18, noise and high point, are dropped
   first: over a village one of those is a bird or a reflection off a window, and a
   single one lifts a cell ten metres.
2. **Close the gaps.** See below. This is the step that decides whether the map is
   flyable.
3. **Smooth once.** A mean over one cell takes the last jaggedness out.
4. **Fill the holes.** A cell with no return at all, which is water or a shadow behind
   a roof, takes the nearest measured height. Not the median of the sheet, which is
   what the raster path uses and which drops a pit into a roof.
5. **Mesh it as terrain.** The existing terrain code does the rest. There is no
   building model in the map at all, and no wall or roof material: a house is the
   laser return off its roof, and its walls are the steep step down to the ground.

## The forest, which is the whole problem

The first build of `suburb-1-scan` was unflyable, and the reason is worth writing
down because it is not obvious and it looks like a bug in the reader.

Woodland is half of that box. Between the branches the beam reaches the ground. So
in one 30 cm cell the highest return is a treetop at 15 m, and in the cell beside it
the highest return is bare earth. Meshed as measured, that is not a canopy. It is a
field of vertical curtains, one for every gap the beam found, and it is the first
thing anybody sees in the map.

The fix is a morphological closing on the finished grid: a maximum window, then a
minimum window of the same size. The maximum closes every gap narrower than the
window. The minimum takes back the growth that caused, so a roof edge and a wall stay
where they were measured. `close_cells = 6`, which is 1.8 m at a 30 cm grid, turns
the curtains into canopy.

The cost is honest: anything thinner than the window survives as a bump and not as a
spike. A mast is worth less than a flyable forest.

## What it is good for, and what it is not

The surface holds one height per cell, so it cannot hold an overhang, an archway, a
bridge deck with anything under it, or the underside of a roof. Flying over a village
that is the right trade. Flying through a gateway it is not.

For that reason the scan is a different kind of map rather than a better one. A
photogrammetry survey gives real two sided geometry over a small area. The LOD2
model gives clean walls a drone can fly between. The scan gives everything that
stands on the ground, over as much ground as you care to download, and no interiors.

## Cost

A 600 m box at a 30 cm grid is 8.0 million triangles and 83 MB, which is inside what
the game was measured to carry: see `docs/benchmark.md`. The two lidar sheets it reads
are about 250 MB each and are cached like every other download.

The grid cell should match the scan. A cell finer than the point spacing invents
detail that was never measured and leaves holes for the fill to guess at. A cell
coarser than the point spacing throws measured detail away. At 23 to 29 points per
square metre, 30 cm is about right and 20 cm is too fine.
