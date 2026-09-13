# Photo textured facades from oblique aerial photos

Date: 2026-09-13. Status: the pipeline builds them. The maps stay on the machine that
builds them.

> **Read this before you run it.** The oblique photos are open data with attribution,
> and the viewer that serves them offers no bulk download. `docs/licensing.md` D6 asks
> anyone using this at scale to write to Maa- ja Ruumiamet first. The code here is published
> so that the method is public and so that the work is ready the day permission
> arrives. It is not published as an invitation to scrape the viewer. That restraint
> is yours to keep: nothing in the code enforces it beyond a rate limit.

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

Tartu old town, a 1 km box, built 2026-09-13 from level 12 tiles at a 9 cm atlas texel:

| | |
|---|---|
| Usable photos found, from five queries | 116 |
| Photos whose fitted pose the orthophoto agrees with | 40 |
| Photos baked from, spread over all eight octants | 22 |
| Wall panels | 9,698 |
| Atlas | 16384 x 6404 px |
| Panels with a photograph of themselves | 5,839 |
| Wall area with a photograph of itself | 60.3 % |
| Remaining panels, borrowing their own building or its neighbour | 3,859 |
| File | 39.7 MB, 538,700 triangles |

Flown, it is convincing from 50 m up and soft in a narrow street. That is the source
and not the code: level 12 tiles are about 18 cm on a wall and they carry the viewer
watermark. "The day permission arrives" below says what changes with the full frames.

## Run it

Everything needed is in this repository. `maps/tartu-old-town-facades.toml` is a
complete worked example over a square kilometre of dense old town.

### 1. Install the extra

The camera resection is a non linear least squares fit, which needs scipy. It is an
optional extra so that a normal map build stays a small install.

```bash
uv sync --extra facades
```

A map with a `[facades]` section built without it stops with a message naming the
extra. No other map is affected.

### 2. Write the map

```toml
[map]
name = "<city>-<place>-facades"
private = true          # required: this map is never published, see below

[buildings]
enabled = true
municipalities = ["Tartu_linn"]
wall_material = "z_concrete2"      # unused while facades are on, kept for the switch back
roof_material = "z_pebbled_asphalt"

[facades]
enabled = true
level = 12              # Deep Zoom level. 13 is the full frame and four times the tiles.
texel_m = 0.09          # atlas resolution on the wall
atlas_px = 16384        # atlas width. It grows in height until every panel fits.
max_candidates = 90     # photos to fit a camera to
max_sources = 22        # photos to bake from, spread over the compass
min_correlation = 0.30  # the orthophoto gate. Below this the pose is wrong.
jpeg_quality = 85
```

Everything else is a normal map: the box, the origin, the terrain and the ground
texture behave exactly as they do without the section.

### 3. Build

```bash
uv run fpv-maps build maps/<name>.toml
```

The first build is slow. It makes five metadata queries, fetches a small frame of
every candidate photo to score it, fits a camera to each, then fetches the chosen
photos at the texture level. Over the Tartu old town that is about two minutes of
requests and four minutes in total.

Every later build is fast, because two things are cached under `data/fotoladu/`:

```
data/fotoladu/
  sources-<map>.json          the chosen photos and their fitted cameras
  <image id>/<level>/<c>_<r>.jpg   every Deep Zoom tile ever fetched
```

Change `texel_m`, `atlas_px` or `jpeg_quality` and the rebuild costs no request at
all. Delete `sources-<map>.json` to choose the photos again, which is what you want
after changing `max_sources`, `max_candidates` or `min_correlation`.

### 4. Read the log

Four numbers say whether it worked.

| Line | Good | Bad, and what it means |
|---|---|---|
| `usable photos` | tens | under 10: the box is outside the flown area |
| `photos with a pose the orthophoto agrees with` | half the candidates | near 0: the orthophoto and the photos disagree, check the ground texture is the same box |
| `photos per direction` | every octant present | one direction only: walls facing away get nothing |
| `wall coverage` | 50 to 65 percent | under 30: the occlusion or the poses are wrong |

Over the Tartu old town on 2026-09-13: 116 usable photos, 40 with an agreed pose, 22
chosen with every octant covered, 60.3 percent of the wall area.

### 5. Install and fly

```bash
uv run fpv-maps build maps/<name>.toml --install
```

The map is a normal custom map. Nothing about it is special to the game.

## The day permission arrives

The pipeline was written to make that day short. Two things change.

**Full resolution frames.** Set `level = 13`, which is the whole 7952 px frame instead
of half of it, and lower `texel_m` to about 0.05. That is the single change that turns
a facade from recognisable into sharp, and the tile cache means only the new level is
fetched. Expect the atlas to reach 16384 px wide by about 12000 tall.

**Exterior orientation.** If the agency supplies the projection centre, the three
rotation angles and the focal length per frame, then steps 2, 3 and 4 of the method
below disappear: no corner ordering to resolve, no resection to fit, no orthophoto to
score against, and no photo thrown away for failing the gate. Build a `Camera`
directly and pass it to the baker.

`fpv_maps.facades.fotoladu.Camera` is the type to fill. It takes the focal length in
pixels, the projection centre as L-EST97 east, north and up, and a 3 x 3 world to
camera rotation whose rows are the camera axes. `Camera.project` is the only thing the
baker calls on it, so anything that fills those fields correctly works. The rest of
the pipeline is unchanged: `sources.frames` fetches the images, `walls.wall_panels`
makes the panels and `bake.bake` fills the atlas.

Every photo would then be usable, not the 34 percent that survive the gate today, and
coverage should rise well above 60 percent.

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
