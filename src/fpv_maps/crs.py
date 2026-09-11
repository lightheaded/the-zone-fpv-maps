"""Coordinate systems.

Geodata is in L-EST97 (EPSG:3301), a metric system. This module always orders
coordinates as (east, north). Heights are EH2000 meters as the data delivers them.

The game uses glTF axes: X east, Y up, Z south. The map origin is a point on the
ground where the game spawns the drone. ``to_game`` maps L-EST97 to game axes.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from pyproj import Transformer

LEST97 = "EPSG:3301"
WGS84 = "EPSG:4326"


@dataclass(frozen=True)
class BBox:
    """Axis aligned box in L-EST97, (east, north) order."""

    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin

    @property
    def center(self) -> tuple[float, float]:
        return ((self.xmin + self.xmax) / 2, (self.ymin + self.ymax) / 2)

    def contains(self, east: float, north: float) -> bool:
        return self.xmin <= east <= self.xmax and self.ymin <= north <= self.ymax

    def buffer(self, meters: float) -> BBox:
        return BBox(self.xmin - meters, self.ymin - meters, self.xmax + meters, self.ymax + meters)

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.xmin, self.ymin, self.xmax, self.ymax)


@lru_cache(maxsize=4)
def _transformer(src: str, dst: str) -> Transformer:
    return Transformer.from_crs(src, dst, always_xy=True)


def wgs84_to_lest97(lat: float, lon: float) -> tuple[float, float]:
    """Return (east, north) in L-EST97 for a WGS84 latitude and longitude."""
    east, north = _transformer(WGS84, LEST97).transform(lon, lat)
    return float(east), float(north)


def lest97_to_wgs84(east: float, north: float) -> tuple[float, float]:
    """Return (lat, lon) in WGS84 for an L-EST97 point."""
    lon, lat = _transformer(LEST97, WGS84).transform(east, north)
    return float(lat), float(lon)


def to_game(points: np.ndarray, origin: tuple[float, float, float]) -> np.ndarray:
    """Map (east, north, height) rows to game axes (x east, y up, z south).

    ``origin`` is (east, north, height) of the game origin.
    """
    pts = np.asarray(points, dtype=np.float64)
    out = np.empty_like(pts)
    out[:, 0] = pts[:, 0] - origin[0]
    out[:, 1] = pts[:, 2] - origin[2]
    out[:, 2] = -(pts[:, 1] - origin[1])
    return out
