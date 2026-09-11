from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from fpv_maps.tour import (
    GroundHeights,
    Shot,
    Tour,
    auto_tour,
    load_tour,
    look_at,
    perspective,
    shot_poses,
    smoothstep,
    still_index,
    sun_direction,
    tour_poses,
)


def flat_ground(height: float = 10.0, span: float = 500.0) -> GroundHeights:
    """A level terrain of ``height`` meters over a square of ``span`` meters."""
    xs, zs = np.mgrid[-span : span + 1 : 25.0, -span : span + 1 : 25.0]
    points = np.stack([xs.ravel(), np.full(xs.size, height), zs.ravel()], axis=1)
    return GroundHeights(points, step=25.0)


def test_smoothstep_ends_and_middle():
    assert smoothstep(0.0) == 0.0
    assert smoothstep(1.0) == 1.0
    assert smoothstep(0.5) == 0.5
    assert smoothstep(-2.0) == 0.0 and smoothstep(2.0) == 1.0


def test_smoothstep_starts_slowly():
    """The first tenth moves less than the middle tenth. That is the ease in."""
    start = smoothstep(0.1) - smoothstep(0.0)
    middle = smoothstep(0.55) - smoothstep(0.45)
    assert start < middle


def test_ground_heights_take_the_highest_point_of_a_cell():
    points = np.array([[0.0, 5.0, 0.0], [1.0, 9.0, 1.0], [100.0, 3.0, 100.0]])
    ground = GroundHeights(points, step=4.0)
    assert ground.at(0.0, 0.0) == 9.0
    assert ground.at(100.0, 100.0) == 3.0


def test_ground_heights_need_vertices():
    with pytest.raises(ValueError, match="no vertices"):
        GroundHeights(np.zeros((0, 3)))


def test_ground_heights_sample_many_points():
    ground = flat_ground(12.0)
    values = ground.sample(np.array([0.0, 100.0]), np.array([0.0, -100.0]))
    assert values.tolist() == [12.0, 12.0]


def test_orbit_keeps_the_radius_and_the_height():
    ground = flat_ground(10.0)
    shot = Shot(
        name="a", kind="orbit", seconds=2.0, target=(0.0, 0.0), radius_m=100.0, height_m=50.0
    )
    poses = list(shot_poses(shot, ground, fps=30))
    assert len(poses) == 60
    for pose in poses:
        assert abs(math.hypot(pose.eye[0], pose.eye[2]) - 100.0) < 1e-6
        assert abs(pose.eye[1] - 60.0) < 1e-6
        assert pose.look == (0.0, 10.0 + shot.look_height_m, 0.0)


def test_reveal_rises_and_pulls_back():
    ground = flat_ground(0.0)
    shot = Shot(
        name="r", kind="reveal", seconds=1.0, target=(0.0, 0.0), radius_m=200.0, height_m=80.0
    )
    poses = list(shot_poses(shot, ground, fps=10))
    first, last = poses[0], poses[-1]
    assert math.hypot(first.eye[0], first.eye[2]) < math.hypot(last.eye[0], last.eye[2])
    assert first.eye[1] < last.eye[1]


def test_fly_goes_from_start_to_end():
    ground = flat_ground(0.0)
    shot = Shot(
        name="f",
        kind="fly",
        seconds=1.0,
        target=(0.0, 0.0),
        start=(-100.0, 0.0),
        end=(100.0, 0.0),
        height_m=30.0,
    )
    poses = list(shot_poses(shot, ground, fps=10))
    assert poses[0].eye[0] == pytest.approx(-100.0)
    assert poses[-1].eye[0] == pytest.approx(100.0)
    assert all(p.eye[1] == pytest.approx(30.0) for p in poses)


def test_a_fly_shot_needs_a_start_and_an_end():
    with pytest.raises(ValueError, match="needs a start and an end"):
        Shot(name="f", kind="fly", seconds=1.0, target=(0.0, 0.0))


def test_an_unknown_shot_kind_stops_the_tour():
    with pytest.raises(ValueError, match="shot kind"):
        Shot(name="x", kind="zoom", seconds=1.0, target=(0.0, 0.0))


def test_a_shot_needs_a_length():
    with pytest.raises(ValueError, match="above 0"):
        Shot(name="x", kind="orbit", seconds=0.0, target=(0.0, 0.0))


def test_the_frame_size_must_be_even():
    with pytest.raises(ValueError, match="even"):
        Tour(name="m", shots=(), width=1921, height=1080)


def test_tour_poses_hold_every_shot():
    ground = flat_ground()
    tour = Tour(
        name="m",
        shots=(
            Shot(name="a", kind="orbit", seconds=1.0, target=(0.0, 0.0)),
            Shot(name="b", kind="orbit", seconds=2.0, target=(0.0, 0.0)),
        ),
        fps=10,
    )
    assert tour.seconds == 3.0
    assert len(list(tour_poses(tour, ground))) == 30
    assert still_index(tour, tour.shots[0]) == 4
    assert still_index(tour, tour.shots[1]) == 20


def test_still_index_needs_a_shot_of_the_tour():
    tour = Tour(name="m", shots=(Shot(name="a", kind="orbit", seconds=1.0, target=(0.0, 0.0)),))
    with pytest.raises(ValueError, match="not a shot"):
        still_index(tour, Shot(name="other", kind="orbit", seconds=1.0, target=(0.0, 0.0)))


def test_look_at_puts_the_target_on_the_view_axis():
    view = look_at(np.array([10.0, 5.0, 0.0]), np.array([0.0, 0.0, 0.0]))
    target = view @ np.array([0.0, 0.0, 0.0, 1.0])
    assert target[0] == pytest.approx(0.0, abs=1e-5)
    assert target[1] == pytest.approx(0.0, abs=1e-5)
    assert target[2] < 0.0
    assert np.allclose(view[:3, :3] @ view[:3, :3].T, np.eye(3), atol=1e-5)


def test_look_at_survives_a_camera_that_looks_straight_down():
    view = look_at(np.array([0.0, 100.0, 0.0]), np.array([0.0, 0.0, 0.0]))
    assert np.isfinite(view).all()


def test_perspective_keeps_the_near_plane():
    matrix = perspective(45.0, 16 / 9, 1.0, 1000.0)
    near = matrix @ np.array([0.0, 0.0, -1.0, 1.0])
    assert near[2] / near[3] == pytest.approx(-1.0, abs=1e-5)


def test_the_sun_stands_above_the_horizon():
    x, y, z = sun_direction()
    assert y > 0.5
    assert math.isclose(math.sqrt(x * x + y * y + z * z), 1.0, rel_tol=1e-9)


def test_auto_tour_holds_an_overview_a_landmark_and_the_spawn():
    ground = flat_ground()
    bounds = (np.array([-500.0, 0.0, -500.0]), np.array([500.0, 60.0, 500.0]))
    tour = auto_tour("m", bounds, ground, [(100.0, -100.0, 40.0)])
    assert [shot.name for shot in tour.shots] == ["overview", "landmark-1", "spawn"]
    assert tour.shots[1].target == (100.0, -100.0)
    assert tour.shots[-1].target == (0.0, 0.0)


TOML = """
[map]
name = "demo"

[area]
bbox = [658000, 6473000, 659000, 6474000]
origin = [658500, 6473500]

[tour]
fps = 30
size = [1280, 720]

[[tour.shot]]
name = "tower"
kind = "orbit"
seconds = 8
target = [658600, 6473700]
radius_m = 150
height_m = 70

[[tour.shot]]
name = "street"
kind = "fly"
seconds = 6
start = [658000, 6473500]
end = [659000, 6473500]
height_m = 30
"""


def test_load_tour_reads_the_shots_in_game_axes(tmp_path: Path):
    path = tmp_path / "demo.toml"
    path.write_text(TOML)
    tour = load_tour(path, "demo", (658500.0, 6473500.0))
    assert tour is not None
    assert tour.fps == 30 and tour.size == (1280, 720)
    assert [shot.name for shot in tour.shots] == ["tower", "street"]
    # East is x, north is minus z.
    assert tour.shots[0].target == (100.0, -200.0)
    assert tour.shots[1].start == (-500.0, 0.0)
    assert tour.shots[1].end == (500.0, 0.0)
    assert tour.shots[1].target == (500.0, 0.0)


def test_load_tour_returns_none_without_a_section(tmp_path: Path):
    path = tmp_path / "plain.toml"
    path.write_text('[map]\nname = "plain"\n')
    assert load_tour(path, "plain", (0.0, 0.0)) is None


def test_load_tour_reads_a_wgs84_target(tmp_path: Path):
    path = tmp_path / "w.toml"
    path.write_text(
        '[tour]\n[[tour.shot]]\nname = "a"\nkind = "orbit"\n'
        "seconds = 4\ntarget_wgs84 = [58.38, 26.72]\n"
    )
    tour = load_tour(path, "w", (658500.0, 6473500.0))
    assert tour is not None
    x, z = tour.shots[0].target
    assert abs(x) < 5000 and abs(z) < 5000


def test_a_fly_shot_can_look_ahead_along_its_own_path():
    ground = flat_ground(0.0)
    shot = Shot(
        name="river",
        kind="fly",
        seconds=1.0,
        target=(0.0, 0.0),
        start=(-400.0, 0.0),
        end=(400.0, 0.0),
        height_m=50.0,
        look_ahead_m=100.0,
        look_height_m=0.0,
    )
    poses = list(shot_poses(shot, ground, fps=10))
    # The camera looks 100 m in front of itself, and never past the end of the path.
    assert poses[0].look[0] == pytest.approx(-300.0)
    assert poses[-1].look[0] == pytest.approx(400.0)
    for pose in poses:
        assert pose.look[0] >= pose.eye[0]


def test_a_fly_shot_without_a_look_ahead_looks_at_the_end():
    ground = flat_ground(0.0)
    shot = Shot(
        name="straight",
        kind="fly",
        seconds=1.0,
        target=(400.0, 0.0),
        start=(-400.0, 0.0),
        end=(400.0, 0.0),
        height_m=50.0,
    )
    looks = {pose.look for pose in shot_poses(shot, ground, fps=5)}
    assert len(looks) == 1
