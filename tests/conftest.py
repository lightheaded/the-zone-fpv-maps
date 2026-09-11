from __future__ import annotations

import numpy as np
import pytest

from fpv_maps.crs import BBox
from fpv_maps.terrain import HeightField


@pytest.fixture
def bbox() -> BBox:
    return BBox(662000, 6473000, 663000, 6474000)


@pytest.fixture
def flat_field(bbox: BBox) -> HeightField:
    """A 1 m grid, 40 m tall everywhere, with a 4 m margin around the box."""
    n = 1008
    return HeightField(
        heights=np.full((n, n), 40.0), west=bbox.xmin - 4, north=bbox.ymax + 4, res=1.0
    )
