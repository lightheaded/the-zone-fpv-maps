"""Copy a built map into the game folder."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

GAME_DIR_ENV = "THE_ZONE_DIR"


def default_game_dir() -> Path | None:
    """The Steam install folder of The Zone on this platform, or None."""
    env = os.environ.get(GAME_DIR_ENV)
    if env:
        return Path(env)
    home = Path.home()
    candidates: list[Path] = []
    if sys.platform == "darwin":
        candidates.append(home / "Library/Application Support/Steam/steamapps/common/The Zone FPV")
    elif sys.platform == "win32":
        program_files = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        candidates.append(Path(program_files) / r"Steam\steamapps\common\The Zone FPV")
    else:
        candidates.append(home / ".steam/steam/steamapps/common/The Zone FPV")
        candidates.append(home / ".local/share/Steam/steamapps/common/The Zone FPV")
    for c in candidates:
        if c.is_dir():
            return c
    return None


def install_map(glb: Path, name: str, game_dir: Path) -> Path:
    """Copy ``glb`` to ``<game>/custom_maps/<name>/<name>.glb`` and return the target."""
    target_dir = game_dir / "custom_maps" / name
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{name}.glb"
    shutil.copyfile(glb, target)
    return target
