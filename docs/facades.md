# Photo textured facades from oblique aerial photos

Date: 2026-09-12. Status: the pipeline builds them. The maps stay on the machine that
builds them. See "What may leave the machine" at the end.

The LOD2 building model of [Maa- ja Ruumiamet](https://geoportaal.maaruum.ee/) gives the shape of every house in
Estonia and nothing of its surface. A map built from it alone gives all 23745
buildings of Tartu the same concrete wall and the same asphalt roof. From the air that
reads well. In a street it reads as a grey model of a city.

The same agency flies oblique photos. [Fotoladu](https://fotoladu.maaamet.ee/) publishes them, four directions per
place, at about 9 cm on the ground. Those photos hold the facades. This document is
how the pipeline gets a facade out of a photo and onto a wall.

## What the service gives, and what it does not

For one ground point the API answers with the photos that see it:

```
https://fotoladu.maaamet.ee/api.php?x=<north>&y=<east>     L-EST97, north first
```

Each record holds the image name, the frame size in pixels, the flight height, the
date, an accuracy code, and **the four corners of the frame on the ground**.

It does not hold the camera position, the angles or the focal length. Without those a
photo cannot be projected onto anything. Everything below exists to recover them.

## Step 1: five queries, not one

The service answers for one point. A single query at the centre of a 1 km box misses
every photo that covers a corner of the box and stops short of the middle. Five
queries, at the centre and the four quarter points, found 116 usable photos over the
Tartu old town where the centre alone found 39.

## Step 2: which published corner is which frame corner

The four corners come as a ring. Nothing says which one is the top left of the frame.
There are eight ways to read a ring of four onto a frame, four rotations times a
mirror, and they are eight different cameras: a quarter turn or a mirror apart.

The corner residual cannot choose between them. Four coplanar points barely determine
a camera at all, so several readings fit to under a pixel on a 7952 pixel frame.
Measured over Tartu, the lowest residual is the right reading about half the time.
That is the fault that put grass and roads on walls in the first attempt.

The orthophoto decides it instead, and it needs no camera to do so. A plane homography
maps the four ground corners onto the four frame corners directly. Project open ground
through each of the eight, sample the photo there, and correlate with the orthophoto at
the same ground points. The right reading wins by a factor of five.

"Open ground" means ground more than 12 m from any building. A wall leans in an oblique
photo, so the ground pixel beside it is not the pixel the orthophoto shows there.

## Step 3: fit the camera

With the reading fixed, a least squares fit recovers focal length, position and the
three angles from the four corners. Two height models are tried, the terrain under each
corner and one plane through their mean, because which fits better depends on the
relief. The corners of one frame lie up to a kilometre apart, so the terrain has to be
read well outside the map box: a 6 m error in a corner height moves a facade by about
60 pixels in the frame, which is more than the facade is tall.

## Step 4: score the camera, and throw most of them away

The same orthophoto correlation now scores the fitted camera, which is a stronger test
than the homography because it uses the relief and not just the plane. Over Tartu a
right pose scores 0.33 to 0.60 and a wrong pose scores about zero. One threshold at
0.30 separates them with room to spare.

Photos looking down from under 25 degrees or over 55 degrees above the horizon are
dropped too: below that a facade gets a very oblique smear and above it a facade gets
almost no pixels.

## Step 5: choose a spread of directions

A wall faces one way, and only a camera on that side of it can see it. So the chosen
set takes the best photo of each compass octant first and fills the rest by score. An
even spread buys more coverage than the same number of the highest scoring photos.

## Step 6: pack and bake

Every near vertical face of every building is grouped by its plane into a flat panel
with a local 2D frame. The panels are shelf packed into one atlas, 8192 px wide and as
tall as it needs, at a fixed texel size on the wall.

Each texel is filled from the best photo that can see it. "Can see it" is three tests:
the wall faces the camera by more than about 70 degrees, the point is inside the frame,
and a ray from the wall to the camera reaches it without passing through another
building. The occlusion test is why a courtyard wall does not get a picture of the
street on the far side of the block.

## Step 7: what has no photo at all

About 44 percent of the wall area of an old town is a courtyard, a light well or a
party wall between two attached houses. No aerial photo sees any of it.

A flat colour there is honest and looks wrong: in a narrow street it is most of what a
pilot sees, and it reads as an untextured map rather than as missing detail. So a panel
with no photo borrows the best covered wall of **its own building**. Both patches use
the same texel size, so the borrowed picture is tiled and never stretched, and a window
stays the size of a window. It is not the true wall. It is the same house, the same age
and the same material, which is a far better guess than grey.

A building where no wall at all got a photo takes the average facade colour of the map.

## Roofs

Roofs take the orthophoto, mapped straight down. It is 10 cm data that already sees
every roof from above, it needs no oblique photo and no fit, and it is what the map
reads like from the air.

## The tile fetch

The viewer serves each frame as [Deep Zoom](https://en.wikipedia.org/wiki/Deep_Zoom) tiles of 256 px. There is no bulk
download. The pipeline stitches one level back into one image and caches every tile
under `data/fotoladu`, so a rebuild costs no request. It fetches at most about 16
tiles a second over four workers.

Level 12 is half of the full 7952 px frame, about 18 cm on a wall at the usual flight
height. Level 13 is the full frame and four times the tiles, for detail that a 20 cm
atlas texel throws away again.

The tiles carry the "Maa-amet" watermark of the viewer, and it bakes into the facades.
Orientation data and unwatermarked frames need the written access that `docs/licensing.md`
D6 asks for.

## What it reaches

Tartu old town, 1 km box, 19 photos of 39 candidates from a single centre query:

| | |
|---|---|
| Wall panels | 9,698 |
| Atlas | 8192 x 2759 px |
| Wall area with a photo | 56.9 % |
| Panels that borrowed their own building | 2,004 |
| File | 30.1 MB, 538,700 triangles |

## What may leave the machine

**The map file may not.** The Fotoladu photos are open data with attribution, but
`docs/licensing.md` D6 records that bulk access needs a written yes that this project
has not asked for yet, and a baked atlas is a derivative of the photos. So:

- The pipeline, this document and the numbers above are published.
- A `.glb` built with `[facades]` on is **not** published: not in a release, not in
  the wiki, not in the repository. `.gitignore` already blocks `dist/`.
- A screenshot or a tour video of such a map is a picture of the photos and is not
  published either.

Ask Maa- ja Ruumiamet first. Until then this is a local capability.
