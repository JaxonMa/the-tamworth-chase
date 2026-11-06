"""Filesystem locations used by the game.

Runtime assets are resolved relative to the repository root so the game can be
started from any working directory.  Player data (save file, exported levels)
lives outside the repository by default and can be redirected with the
``TAMWORTH_CHASE_DATA`` environment variable, which is handy for tests.

The project used to be called "The Tamworth Two".  Save files from that era live
in ``~/.the_tamworth_two``; :func:`legacy_save_path` exposes them so the save
layer can migrate them once instead of silently losing player progress.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "The Tamworth Chase"
DATA_DIR_ENV = "TAMWORTH_CHASE_DATA"
LEGACY_DATA_DIR_ENV = "TAMWORTH_TWO_DATA"
DATA_DIR_NAME = ".the_tamworth_chase"
LEGACY_DATA_DIR_NAME = ".the_tamworth_two"
_SAVE_FILE_NAME = "save.json"


def project_root() -> Path:
    """Return the repository root (the directory that contains ``main.py``)."""
    return Path(__file__).resolve().parent.parent


def asset_path(*parts: str) -> Path:
    return project_root().joinpath("assets", *parts)


def data_override() -> str:
    """Return the data directory override, including the legacy variable."""
    return os.environ.get(DATA_DIR_ENV) or os.environ.get(LEGACY_DATA_DIR_ENV) or ""


def data_dir() -> Path:
    """Return the writable directory that holds the save file."""
    override = data_override()
    if override:
        return Path(override).expanduser()
    return Path.home() / DATA_DIR_NAME


def legacy_data_dir() -> Path:
    """Return the pre-rename data directory (never created automatically)."""
    override = os.environ.get(LEGACY_DATA_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / LEGACY_DATA_DIR_NAME


def ensure_data_dir() -> Path:
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_path() -> Path:
    return data_dir() / _SAVE_FILE_NAME


def legacy_save_path() -> Path:
    return legacy_data_dir() / _SAVE_FILE_NAME


def custom_levels_dir() -> Path:
    """Directory where the editor exports custom levels."""
    directory = project_root() / "custom_levels"
    return directory
