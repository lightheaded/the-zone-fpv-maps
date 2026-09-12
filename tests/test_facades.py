"""The facade pipeline, without a single network request.

Every test builds its own photo from a camera it knows, so the answer is known before
the code runs. That is the only way to test a resection: a real photo has no truth to
compare against, which is the whole reason the orthophoto check exists.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from fpv_maps.buildings import Building, BuildingSet
from fpv_maps.crs import BBox
from fpv_maps.facades import bake, orthocheck, tiles
from fpv_maps.facades.fotoladu import Camera, Photo, _axes, resect_candidates
from fpv_maps.facades.walls import wall_panels

BOX = BBox(658750, 6473850, 659750, 6474850)
GROUND_Z = 40.0


# --------------------------------------------------------------------- a fake camera


def make_camera(
    east: float = 659221.0,
    north: float = 6473000.0,
    height: float = 900.0,
    azimuth_deg: float = 0.0,
    tilt_deg: float = 45.0,
    f_px: float = 13000.0,
    width: int = 7952,
    height_px: int = 5304,
) -> Camera:
    """A camera at ``azimuth_deg``, tilted ``tilt_deg`` away from straight down."""
    return Camera(
        f_px=f_px,
        centre=np.array([east, north, GROUND_Z + height]),
        rotation=_axes(math.radians(azimuth_deg), math.radians(tilt_deg), 0.0),
        width=width,
        height=height_px,
        rms_px=0.0,
        tilt_deg=tilt_deg,
        ground_z=GROUND_Z,
    )


def photo_of(camera: Camera, date: str = "2024-04-27") -> Photo:
    """The record the service would publish for this camera: its four ground corners.

    The corners are written in the ring order the API uses, which is not the order of
    the frame. Recovering that order is what ``best_ordering`` is for.
    """
    w, h = camera.width / 2.0, camera.height / 2.0
    corners = []
    for u, v in ((-w, -h), (-w, h), (w, h), (w, -h)):
        # Invert the projection onto the plane z = GROUND_Z.
        ray = np.array([u / camera.f_px, v / camera.f_px, 1.0]) @ camera.rotation
        t = (GROUND_Z - camera.centre[2]) / ray[2]
        p = camera.centre + t * ray
        corners.append((float(p[0]), float(p[1])))
    return Photo(
        id="1",
        image="2024/a7r4/x/0001",
        rada="2024/a7r4",
        width=camera.width,
        height=camera.height,
        corners=tuple(corners),
        korgus_m=camera.centre[2],
        date=date,
        accuracy=2,
        tiled=True,
    )


# ------------------------------------------------------------------------- resection


def test_the_resection_recovers_the_camera_that_made_the_corners():
    truth = make_camera()
    photo = photo_of(truth)
    cams = resect_candidates(photo, ground_z=GROUND_Z, orderings=[(0, False)])
    assert cams, "the fit found no camera for the ordering that made the photo"
    best = min(cams, key=lambda c: float(np.linalg.norm(c.centre - truth.centre)))
    assert np.linalg.norm(best.centre - truth.centre) < 5.0
    assert abs(best.f_px - truth.f_px) < 100.0


def test_a_wrong_corner_ordering_still_fits_the_corners():
    """The reason the corner residual cannot choose the pose, as a test.

    If this ever fails because only one ordering fits, the orthophoto check has become
    unnecessary. It has not so far: several readings fit to well under a pixel.
    """
    photo = photo_of(make_camera())
    fits = {
        (rot, rev): resect_candidates(photo, ground_z=GROUND_Z, orderings=[(rot, rev)])
        for rot in range(4)
        for rev in (False, True)
    }
    good = [k for k, v in fits.items() if v and min(c.rms_px for c in v) < 1.0]
    assert len(good) > 1, f"only {good} fit, the ambiguity this pipeline handles is gone"


def test_the_projection_puts_the_frame_corners_where_the_photo_says():
    camera = make_camera()
    photo = photo_of(camera)
    pts = np.array([[e, n, GROUND_Z] for e, n in photo.corners])
    uv, depth = camera.project(pts)
    assert (depth > 0).all()
    assert np.allclose(np.abs(uv[:, 0]), camera.width / 2.0, atol=1e-3)
    assert np.allclose(np.abs(uv[:, 1]), camera.height / 2.0, atol=1e-3)


# ------------------------------------------------------------------------ homography


def test_the_homography_maps_the_four_points_it_was_built_from():
    src = [(0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)]
    dst = [(-100.0, -50.0), (100.0, -50.0), (100.0, 50.0), (-100.0, 50.0)]
    mat = orthocheck.homography(src, dst)
    for (x, y), (u, v) in zip(src, dst, strict=True):
        q = mat @ np.array([x, y, 1.0])
        assert abs(q[0] / q[2] - u) < 1e-6
        assert abs(q[1] / q[2] - v) < 1e-6


def test_the_right_corner_ordering_wins_against_the_orthophoto():
    """Build a photo from a known camera, then let the code find the ordering."""
    rng = np.random.default_rng(7)
    camera = make_camera()
    photo = photo_of(camera)
    # Ground points inside the frame, with a random brightness each.
    pts = np.column_stack(
        [
            rng.uniform(BOX.xmin, BOX.xmax, 3000),
            rng.uniform(BOX.ymin, BOX.ymax, 3000),
            np.full(3000, GROUND_Z),
        ]
    )
    lum = rng.uniform(0, 255, len(pts))
    # Paint them into a small image through the true camera, which is the photo.
    scale = 994 / camera.width
    w = int(camera.width * scale)
    h = int(camera.height * scale)
    image = np.zeros((h, w), np.float32)
    uv, depth = camera.project(pts)
    x = ((uv[:, 0] + camera.width / 2.0) * scale).astype(int)
    y = ((uv[:, 1] + camera.height / 2.0) * scale).astype(int)
    ok = (depth > 0) & (x >= 1) & (x < w - 1) & (y >= 1) & (y < h - 1)
    for xi, yi, li in zip(x[ok], y[ok], lum[ok], strict=True):
        image[yi - 1 : yi + 2, xi - 1 : xi + 2] = li
    ranked = orthocheck.best_ordering(photo, image, scale, (0, 0), pts, lum)
    assert ranked[0][1:] == (0, False), f"picked {ranked[0]}, second was {ranked[1]}"
    assert ranked[0][0] > 3 * max(r[0] for r in ranked[1:])
    # The same camera scores well and a quarter turn of it scores nothing.
    assert orthocheck.score(camera, image, scale, (0, 0), pts, lum)[0] > 0.5
    turned = make_camera(azimuth_deg=90.0)
    assert orthocheck.score(turned, image, scale, (0, 0), pts, lum)[0] < 0.2


# ----------------------------------------------------------------------------- walls


def box_building(name: str, east: float, north: float, side: float, height: float) -> Building:
    """A closed box on the ground, wound so that every face points out."""
    x0, x1 = east, east + side
    y0, y1 = north, north + side
    z0, z1 = GROUND_Z, GROUND_Z + height
    v = np.array(
        [
            [x0, y0, z0],
            [x1, y0, z0],
            [x1, y1, z0],
            [x0, y1, z0],
            [x0, y0, z1],
            [x1, y0, z1],
            [x1, y1, z1],
            [x0, y1, z1],
        ],
        float,
    )
    f = np.array(
        [
            [0, 2, 1],
            [0, 3, 2],  # floor
            [4, 5, 6],
            [4, 6, 7],  # roof
            [0, 1, 5],
            [0, 5, 4],  # south
            [1, 2, 6],
            [1, 6, 5],  # east
            [2, 3, 7],
            [2, 7, 6],  # north
            [3, 0, 4],
            [3, 4, 7],  # west
        ]
    )
    return Building(name=name, vertices=v, faces=f)


def test_a_box_gives_four_walls_that_face_outward():
    b = box_building("b1", 659000, 6474000, 12.0, 9.0)
    panels = wall_panels(BuildingSet(buildings=[b]))
    assert len(panels) == 4
    centre = np.array([659006.0, 6474006.0])
    for p in panels:
        assert abs(p.width - 12.0) < 1e-6
        assert abs(p.height - 9.0) < 1e-6
        assert abs(p.normal[2]) < 1e-9
        mid = p.origin + p.u_axis * p.width / 2 + p.v_axis * p.height / 2
        away = mid[:2] - centre
        assert float(np.dot(p.normal[:2], away)) > 0, "a wall normal points into the box"


def test_a_panel_maps_its_own_corners_to_its_own_size():
    b = box_building("b1", 659000, 6474000, 12.0, 9.0)
    p = wall_panels(BuildingSet(buildings=[b]))[0]
    uv = p.to_uv(p.tris.reshape(-1, 3))
    assert uv[:, 0].min() == pytest.approx(0.0, abs=1e-6)
    assert uv[:, 0].max() == pytest.approx(p.width, abs=1e-6)
    assert uv[:, 1].min() == pytest.approx(0.0, abs=1e-6)
    assert uv[:, 1].max() == pytest.approx(p.height, abs=1e-6)


def test_a_flat_roof_makes_no_wall_panel():
    """A face that lies down is a roof. Only near vertical faces become panels."""
    b = box_building("b1", 659000, 6474000, 12.0, 0.4)
    panels = wall_panels(BuildingSet(buildings=[b]), min_area=6.0)
    assert panels == []


# ------------------------------------------------------------------------- the atlas


def test_the_pack_keeps_every_panel_inside_the_atlas_and_apart():
    rng = np.random.default_rng(3)
    buildings = [
        box_building(f"b{i}", 659000 + 40 * i, 6474000, float(rng.uniform(8, 30)), 12.0)
        for i in range(12)
    ]
    panels = wall_panels(BuildingSet(buildings=buildings))
    width, height = bake.pack(panels, texel_m=0.25, max_px=1024)
    assert width == 1024
    occupied = np.zeros((height, width), bool)
    for p in panels:
        x0, y0 = p.uv0
        pw, ph = p.px
        assert x0 + pw <= width and y0 + ph <= height
        assert not occupied[y0 : y0 + ph, x0 : x0 + pw].any(), "two panels share texels"
        occupied[y0 : y0 + ph, x0 : x0 + pw] = True


def test_a_panel_gets_at_least_one_texel_per_texel_metre():
    b = box_building("b1", 659000, 6474000, 20.0, 10.0)
    panels = wall_panels(BuildingSet(buildings=[b]))
    bake.pack(panels, texel_m=0.5, max_px=4096)
    for p in panels:
        assert p.px[0] >= p.width / 0.5
        assert p.px[1] >= p.height / 0.5


# ------------------------------------------------------------------------ deep zoom


def test_the_deep_zoom_level_sizes_halve():
    photo = photo_of(make_camera())
    assert tiles.level_for(photo) == 13
    assert tiles.level_size(photo, 13) == (7952, 5304)
    assert tiles.level_size(photo, 12) == (3976, 2652)
    assert tiles.level_size(photo, 10) == (994, 663)


def test_a_level_above_the_full_frame_is_clamped():
    photo = photo_of(make_camera())
    assert tiles.level_for(photo, 20) == 13
