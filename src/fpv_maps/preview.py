"""A top-down preview image of a built map: the ground texture with building outlines.

The preview lets a person see a map before they install it. The release page and the
README show it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh
from PIL import ImageDraw

from fpv_maps.crs import BBox

ROOF_COLOR = (255, 60, 40)


def render_preview(
    terrain: trimesh.Trimesh,
    roofs: trimesh.Trimesh | None,
    bbox: BBox,
    origin: tuple[float, float, float],
    path: Path,
    size_px: int = 1600,
    quality: int = 82,
) -> Path:
    """Draw the terrain texture scaled to ``size_px`` and outline every roof triangle."""
    image = terrain.visual.material.baseColorTexture.convert("RGB")
    image = image.resize((size_px, int(size_px * bbox.height / bbox.width)))
    if roofs is not None and len(roofs.faces):
        draw = ImageDraw.Draw(image)
        sx = image.width / bbox.width
        sy = image.height / bbox.height
        west = bbox.xmin - origin[0]
        north = -(bbox.ymax - origin[1])
        tri = roofs.vertices[roofs.faces]
        px = np.stack([(tri[:, :, 0] - west) * sx, (tri[:, :, 2] - north) * sy], axis=-1)
        for t in px:
            draw.polygon([tuple(p) for p in t], outline=ROOF_COLOR)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="JPEG", quality=quality, optimize=True)
    return path
