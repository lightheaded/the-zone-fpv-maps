from __future__ import annotations

import math

import numpy as np
import trimesh

from fpv_maps.course import Gate, build_course, check_clearance, course_length_m


def flat_ground(x: float, z: float) -> float:
    return 0.0


def test_course_length_closes_the_lap():
    gates = (
        Gate(east=0.0, north=0.0),
        Gate(east=30.0, north=0.0),
        Gate(east=30.0, north=40.0),
    )
    # 30 east, then 40 north, then 50 back on the diagonal.
    assert course_length_m(gates) == 120.0


def test_course_length_of_one_gate_is_zero():
    assert course_length_m((Gate(east=0.0, north=0.0),)) == 0.0


def test_build_course_places_every_bar():
    gates = (Gate(east=10.0, north=20.0, height_m=6.0, size_m=5.0),)
    origin = (0.0, 0.0, 0.0)
    meshes = build_course(gates, origin, flat_ground)
    assert set(meshes) == {
        "course_gate01_left",
        "course_gate01_right",
        "course_gate01_top",
        "course_gate01_bottom",
    }
    # Game axes: x east, y up, z south. The gate stands 6 m over flat ground.
    centre = np.vstack([np.asarray(m.vertices) for m in meshes.values()]).mean(axis=0)
    assert math.isclose(centre[0], 10.0, abs_tol=1e-6)
    assert math.isclose(centre[1], 6.0, abs_tol=1e-6)
    assert math.isclose(centre[2], -20.0, abs_tol=1e-6)


def test_build_course_opening_is_the_asked_size():
    gates = (Gate(east=0.0, north=0.0, height_m=10.0, size_m=5.0, bar_m=0.25),)
    meshes = build_course(gates, (0.0, 0.0, 0.0), flat_ground)
    left = np.asarray(meshes["course_gate01_left"].vertices)
    right = np.asarray(meshes["course_gate01_right"].vertices)
    # The inner faces of the two posts are 5 m apart.
    assert math.isclose(right[:, 0].min() - left[:, 0].max(), 5.0, abs_tol=1e-6)


def test_yaw_turns_the_gate_about_the_vertical():
    straight = build_course((Gate(east=0.0, north=0.0, yaw_deg=0.0),), (0, 0, 0), flat_ground)
    turned = build_course((Gate(east=0.0, north=0.0, yaw_deg=90.0),), (0, 0, 0), flat_ground)
    # A gate flown north is wide in x. Turned by 90 degrees it is wide in z.
    a = np.asarray(straight["course_gate01_left"].vertices).mean(axis=0)
    b = np.asarray(turned["course_gate01_left"].vertices).mean(axis=0)
    assert abs(a[0]) > 2.0 and abs(a[2]) < 1e-6
    assert abs(b[0]) < 1e-6 and abs(b[2]) > 2.0
    assert math.isclose(a[1], b[1], abs_tol=1e-6)


def test_check_clearance_finds_a_blocked_gate():
    gates = (
        Gate(east=0.0, north=0.0, height_m=5.0, size_m=6.0),
        Gate(east=50.0, north=0.0, height_m=5.0, size_m=6.0),
    )
    origin = (0.0, 0.0, 0.0)
    # A box right in the opening of gate 1 and nothing near gate 2.
    blocker = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    blocker.apply_translation((0.0, 5.0, 0.0))
    report = check_clearance(gates, origin, flat_ground, {"tree": blocker})
    assert report[0]["clear"] is False
    assert report[0]["in_opening"] == 8
    assert report[1]["clear"] is True


def test_check_clearance_ignores_the_course_itself():
    gates = (Gate(east=0.0, north=0.0, height_m=5.0, size_m=6.0),)
    origin = (0.0, 0.0, 0.0)
    course = build_course(gates, origin, flat_ground)
    # The bars of the gate frame sit on the edge of the opening, and they must never
    # count as an obstacle, or every gate would report itself as blocked.
    assert check_clearance(gates, origin, flat_ground, course)[0]["clear"] is True


def test_check_clearance_without_obstacles_reports_every_gate_clear():
    # An empty report would read as "nothing blocked" by accident. Say it plainly.
    report = check_clearance((Gate(east=0.0, north=0.0),), (0, 0, 0), flat_ground, {})
    assert report == [{"gate": 1, "in_opening": 0, "in_approach": 0, "clear": True}]
