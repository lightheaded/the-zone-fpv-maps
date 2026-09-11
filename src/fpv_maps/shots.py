"""Prepare in-game screenshots for the documentation.

The game has no free camera and no command line option that loads a map, so a person
flies the map and captures the pictures. This module does the rest: it scales every
picture to the documentation width, drops the metadata and gives it the correct name.
The metadata of a screenshot can hold a user name and a machine name, so it never goes
into the repository. See the first pillar in ``AGENTS.md``.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PIL import Image

SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")


def collect(sources: Iterable[Path]) -> list[Path]:
    """Every picture in ``sources``, oldest first. A folder gives its own pictures."""
    found: list[Path] = []
    for source in sources:
        if source.is_dir():
            found.extend(p for p in source.iterdir() if p.suffix.lower() in SUFFIXES)
        elif source.suffix.lower() in SUFFIXES:
            found.append(source)
        else:
            raise ValueError(f"{source} is not a picture. Use one of {list(SUFFIXES)}.")
    return sorted(found, key=lambda p: (p.stat().st_mtime, p.name))


def clean_image(path: Path, width: int) -> Image.Image:
    """Open one picture, drop every metadata block and scale it to ``width`` pixels."""
    with Image.open(path) as raw:
        image = raw.convert("RGB")
    if image.width != width:
        height = max(1, round(image.height * width / image.width))
        image = image.resize((width, height), Image.LANCZOS)
    # A new image from the pixels only. It carries no EXIF block and no comment.
    clean = Image.frombytes("RGB", image.size, image.tobytes())
    return clean


def import_shots(
    sources: Iterable[Path],
    name: str,
    out_dir: Path,
    width: int = 1600,
    quality: int = 88,
    start: int = 1,
) -> list[Path]:
    """Write every picture as ``<out_dir>/<name>-ingame-<number>.jpg`` and return the paths.

    ``start`` is the number of the first picture, so that a second run can add pictures
    to a map that has some.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for offset, source in enumerate(collect(sources)):
        target = out_dir / f"{name}-ingame-{start + offset}.jpg"
        clean_image(source, width).save(target, format="JPEG", quality=quality, optimize=True)
        written.append(target)
    return written


def next_number(out_dir: Path, name: str) -> int:
    """The next free number of ``<name>-ingame-<number>.jpg`` in ``out_dir``."""
    numbers = []
    for path in out_dir.glob(f"{name}-ingame-*.jpg"):
        tail = path.stem.rsplit("-", 1)[-1]
        if tail.isdigit():
            numbers.append(int(tail))
    return max(numbers, default=0) + 1
