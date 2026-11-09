"""Bundled background music and AudioManager behaviour."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.audio import MUSIC_GAIN, AudioManager

ROOT = Path(__file__).resolve().parent.parent
MUSIC = ROOT / "assets" / "music" / "meadow_thoughts.ogg"


@pytest.fixture(autouse=True)
def stop_music():
    yield
    try:
        pygame.mixer.music.stop()
    except pygame.error:
        pass


def test_bundled_music_asset_is_valid_ogg():
    assert MUSIC.is_file()
    data = MUSIC.read_bytes()
    assert data[:4] == b"OggS"
    assert 2_000_000 < len(data) < 3_000_000
    notes = (MUSIC.parent / "README.md").read_text(encoding="utf-8")
    assert "Meadow Thoughts" in notes
    assert "CC0" in notes


def test_music_starts_and_follows_master_sound():
    audio = AudioManager(enabled=True, volume=0.6)
    if not audio.available or not audio.music_available:
        pytest.skip("audio mixer unavailable")

    assert audio.music_started is True
    assert audio.music_paused is False
    assert pygame.mixer.music.get_busy() is True

    audio.set_enabled(False)
    assert audio.music_paused is True

    audio.set_enabled(True)
    assert audio.music_paused is False

    audio.set_volume(0.4)
    assert pygame.mixer.music.get_volume() == pytest.approx(0.4 * MUSIC_GAIN, abs=0.02)


def test_music_waits_for_sound_to_be_enabled():
    audio = AudioManager(enabled=False, volume=0.6)
    if not audio.available or not audio.music_available:
        pytest.skip("audio mixer unavailable")

    assert audio.music_available is True
    assert audio.music_started is False

    audio.set_enabled(True)
    assert audio.music_started is True
    assert audio.music_paused is False


def test_missing_music_file_does_not_break_sound_effects(tmp_path: Path):
    audio = AudioManager(music_path=tmp_path / "missing.ogg")
    if not audio.available:
        pytest.skip("audio mixer unavailable")

    assert audio.sounds
    assert audio.music_available is False
    assert audio.music_started is False

    audio.set_enabled(False)
    audio.set_enabled(True)
    audio.play("click")
    assert audio.music_started is False
