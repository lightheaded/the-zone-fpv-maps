"""A top-down preview image of a built map: the ground texture with the roofs marked.

The preview lets a person see a map before they install it. The release page and the
README show it. A city map has hundreds of thousands of roof triangles, so the roofs
are filled into one mask and blended once, not outlined one by one.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw

from fpv_maps.crs import BBox

ROOF_COLOR = (255, 60, 40)
ROOF_ALPHA = 0.45


def render_preview(
    ground: Image.Image | np.ndarray,
    roofs: Iterable[trimesh.Trimesh],
    bbox: BBox,
    origin: tuple[float, float, float],
    path: Path,
    size_px: int = 1600,
    quality: int = 82,
) -> Path:
    """Scale the ground texture to ``size_px`` wide and tint every roof triangle red.

    ``roofs`` are meshes in game axes. ``origin`` is their L-EST97 anchor, so that the
    x and z of a vertex map back into ``bbox``.
    """
    image = ground if isinstance(ground, Image.Image) else Image.fromarray(ground, mode="RGB")
    image = image.convert("RGB")
    image = image.resize((size_px, max(1, int(size_px * bbox.height / bbox.width))))

    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    level = int(round(255 * ROOF_ALPHA))
    scale_x = image.width / bbox.width
    scale_y = image.height / bbox.height
    west = bbox.xmin - origin[0]
    north = -(bbox.ymax - origin[1])
    drawn = 0
    for mesh in roofs:
        if mesh is None or not len(mesh.faces):
            continue
        tri = mesh.vertices[mesh.faces]
        px = np.stack([(tri[:, :, 0] - west) * scale_x, (tri[:, :, 2] - north) * scale_y], axis=-1)
        for corners in px:
            draw.polygon([(float(a), float(b)) for a, b in corners], fill=level)
        drawn += len(px)

    if drawn:
        image = Image.composite(Image.new("RGB", image.size, ROOF_COLOR), image, mask)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="JPEG", quality=quality, optimize=True)
    return path
