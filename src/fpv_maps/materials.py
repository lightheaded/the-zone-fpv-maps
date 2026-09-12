"""Materials for the exported glTF.

The Zone ships a Blender template with 382 materials named ``z_<texture>``. The game
replaces a material by name at load time, so a mesh that uses such a name gets the
in-game texture. Any other material name keeps the color and texture from the file.
"""

from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image
from trimesh.visual.material import PBRMaterial

TEMPLATE_PREFIX = "z_"

#: The largest texture that Godot accepts is 16384 px square, which is 268 megapixels.
#: Pillow refuses an image over 179 megapixels by default, because an image that large
#: from an unknown source is a denial of service. Every image this pipeline opens it
#: wrote itself a moment earlier, or it comes from the survey of the person running the
#: build, so the guard only has to stay above the engine limit.
Image.MAX_IMAGE_PIXELS = 16384 * 16384


def is_template_material(name: str) -> bool:
    return name.startswith(TEMPLATE_PREFIX)


def srgb_to_linear(value: int) -> float:
    """One sRGB channel, 0 to 255, to linear light, 0.0 to 1.0."""
    c = value / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def color_material(name: str, rgb: tuple[int, int, int], roughness: float = 0.9) -> PBRMaterial:
    """Flat color, no texture. ``rgb`` is sRGB as a person reads it.

    glTF stores ``baseColorFactor`` in linear light. The first test tile wrote sRGB
    values into it, and the game showed a red box as pink and an orange gate as yellow.
    """
    return PBRMaterial(
        name=name,
        baseColorFactor=[srgb_to_linear(c) for c in rgb] + [1.0],
        metallicFactor=0.0,
        roughnessFactor=roughness,
    )


def template_material(name: str) -> PBRMaterial:
    """A material that the game replaces. The gray color is the fallback when it does not."""
    if not is_template_material(name):
        raise ValueError(f"template material names start with {TEMPLATE_PREFIX!r}: {name!r}")
    return color_material(name, (150, 150, 150))


def jpeg_image(rgb: np.ndarray, quality: int) -> Image.Image:
    """Encode an RGB array as JPEG and reopen it, so that trimesh embeds the JPEG bytes."""
    buf = BytesIO()
    Image.fromarray(rgb, mode="RGB").save(buf, format="JPEG", quality=quality, optimize=True)
    buf.seek(0)
    img = Image.open(buf)
    img.load()
    return img


def texture_material(name: str, image: Image.Image) -> PBRMaterial:
    return PBRMaterial(
        name=name,
        baseColorTexture=image,
        metallicFactor=0.0,
        roughnessFactor=1.0,
    )


def checker_image(size: int = 256, cells: int = 8) -> Image.Image:
    """Orange and white checker board, a PNG texture for the probe box."""
    cell = size // cells
    yy, xx = np.mgrid[0:size, 0:size]
    odd = ((yy // cell) + (xx // cell)) % 2 == 1
    rgb = np.where(odd[..., None], [255, 120, 0], [250, 250, 250]).astype(np.uint8)
    buf = BytesIO()
    Image.fromarray(rgb, mode="RGB").save(buf, format="PNG")
    buf.seek(0)
    img = Image.open(buf)
    img.load()
    return img
