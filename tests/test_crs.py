import numpy as np

from fpv_maps.crs import BBox, lest97_to_wgs84, to_game, wgs84_to_lest97


def test_wgs84_roundtrip_annelinn():
    east, north = wgs84_to_lest97(58.3747, 26.7726)
    # Verified against the Maa-amet 1:2000 grid: this point is in sheet 473662.
    assert 662000 < east < 663000
    assert 6473000 < north < 6474000
    lat, lon = lest97_to_wgs84(east, north)
    assert abs(lat - 58.3747) < 1e-6
    assert abs(lon - 26.7726) < 1e-6


def test_to_game_axes():
    origin = (100.0, 200.0, 50.0)
    pts = np.array([[100.0, 200.0, 50.0], [110.0, 200.0, 50.0], [100.0, 210.0, 55.0]])
    out = to_game(pts, origin)
    assert np.allclose(out[0], [0, 0, 0])
    assert np.allclose(out[1], [10, 0, 0])  # east is +x
    assert np.allclose(out[2], [0, 5, -10])  # north is -z, height is +y


def test_bbox_helpers():
    b = BBox(0, 0, 10, 20)
    assert b.width == 10 and b.height == 20
    assert b.center == (5, 10)
    assert b.contains(5, 5) and not b.contains(11, 5)
    assert b.buffer(1).as_tuple() == (-1, -1, 11, 21)
