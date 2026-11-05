"""Filesystem locations used by the game.

Runtime assets are resolved relative to the repository root so the game can be
started from any working directory.  Player data (save file, exported levels)
lives outside the repository by default and can be redirected with the
``TAMWORTH_TWO_DATA`` environment variable, which is handy for tests.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "The Tamworth Two"
DATA_DIR_ENV = "TAMWORTH_TWO_DATA"
_SAVE_FILE_NAME = "save.json"


def project_root() -> Path:
    """Return the repository root (the directory that contains ``main.py``)."""
    return Path(__file__).resolve().parent.parent


def asset_path(*parts: str) -> Path:
    return project_root().joinpath("assets", *parts)


def data_dir() -> Path:
    """Return the writable directory that holds the save file."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".the_tamworth_two"


def ensure_data_dir() -> Path:
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_path() -> Path:
    return data_dir() / _SAVE_FILE_NAME


def custom_levels_dir() -> Path:
    """Directory where the editor exports custom levels."""
    directory = project_root() / "custom_levels"
    return directory
