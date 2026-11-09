"""Procedural sound effects plus a bundled CC0 background loop.

The short cues are synthesised at start-up from simple waveforms; the gentle
harp loop ships locally in ``assets/music``.  Sound and music share the settings
master switch and volume.  A missing audio device or music file is tolerated
silently.
"""

from __future__ import annotations

import math
from array import array
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pygame

from .paths import asset_path

SAMPLE_RATE = 44100
MUSIC_RELATIVE_PATH = ("music", "meadow_thoughts.ogg")
MUSIC_GAIN = 0.30


def _envelope(index: int, total: int, attack: float = 0.02, release: float = 0.4) -> float:
    attack_samples = max(1, int(total * attack))
    release_samples = max(1, int(total * release))
    if index < attack_samples:
        return index / attack_samples
    if index > total - release_samples:
        return max(0.0, (total - index) / release_samples)
    return 1.0


def _tone(frequency: float, duration: float, amplitude: float = 0.35, harmonic: float = 0.35) -> List[float]:
    total = int(SAMPLE_RATE * duration)
    samples: List[float] = []
    for index in range(total):
        t = index / SAMPLE_RATE
        value = math.sin(2 * math.pi * frequency * t)
        value += harmonic * math.sin(4 * math.pi * frequency * t)
        value *= _envelope(index, total)
        samples.append(value * amplitude)
    return samples


def _silence(duration: float) -> List[float]:
    return [0.0] * int(SAMPLE_RATE * duration)


def _mix_sequence(parts: Sequence[Sequence[float]], gap: float = 0.0) -> List[float]:
    output: List[float] = []
    for part in parts:
        output.extend(part)
        if gap:
            output.extend(_silence(gap))
    return output


def _to_bytes(samples: Sequence[float]) -> bytes:
    data = array("h")
    for sample in samples:
        clipped = max(-1.0, min(1.0, sample))
        data.append(int(clipped * 32767))
    return data.tobytes()


def _build_cues() -> Dict[str, bytes]:
    cues: Dict[str, bytes] = {}

    cues["click"] = _to_bytes(_tone(880, 0.055, 0.25, 0.2))

    place = _tone(320, 0.08, 0.3, 0.6)
    for index in range(len(place)):
        place[index] *= 1.0 - 0.7 * (index / len(place))
    cues["place"] = _to_bytes(place)
    cues["undo"] = _to_bytes(_tone(420, 0.07, 0.22, 0.4))

    cues["start"] = _to_bytes(_mix_sequence([_tone(523, 0.09, 0.3), _tone(784, 0.12, 0.3)], 0.01))

    cues["win"] = _to_bytes(
        _mix_sequence(
            [_tone(523, 0.12, 0.32), _tone(659, 0.12, 0.32), _tone(784, 0.16, 0.34), _tone(1046, 0.3, 0.36)],
            0.02,
        )
    )
    cues["lose"] = _to_bytes(_mix_sequence([_tone(392, 0.16, 0.26), _tone(294, 0.3, 0.26)], 0.02))
    cues["loop"] = _to_bytes(
        _mix_sequence(
            [_tone(440, 0.1, 0.24), _tone(415, 0.1, 0.24), _tone(392, 0.1, 0.24), _tone(370, 0.24, 0.24)],
            0.01,
        )
    )
    cues["unlock"] = _to_bytes(
        _mix_sequence([_tone(784, 0.08, 0.22), _tone(988, 0.08, 0.22), _tone(1318, 0.18, 0.24)], 0.01)
    )
    cues["error"] = _to_bytes(_tone(180, 0.12, 0.2, 0.8))
    return cues


class AudioManager:
    """Tiny wrapper around ``pygame.mixer`` with graceful degradation."""

    def __init__(
        self,
        enabled: bool = True,
        volume: float = 0.6,
        music_path: Optional[Path] = None,
    ) -> None:
        self.enabled = enabled
        self.volume = max(0.0, min(1.0, volume))
        self.available = False
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        self.music_path = (
            Path(music_path)
            if music_path is not None
            else asset_path(*MUSIC_RELATIVE_PATH)
        )
        self.music_available = False
        self.music_started = False
        self.music_paused = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=512)
            self.available = True
        except pygame.error:
            self.available = False
            return
        try:
            raw = _build_cues()
            for name, data in raw.items():
                sound = pygame.mixer.Sound(buffer=data)
                sound.set_volume(self.volume)
                self.sounds[name] = sound
        except (pygame.error, ValueError):
            self.available = False
            return
        self._load_music()

    def _load_music(self) -> None:
        try:
            if not self.music_path.is_file():
                return
            pygame.mixer.music.load(str(self.music_path))
            pygame.mixer.music.set_volume(self.volume * MUSIC_GAIN)
        except (pygame.error, OSError):
            return
        self.music_available = True
        if self.enabled:
            self._start_music(fade_ms=1200)

    def _start_music(self, fade_ms: int = 600) -> None:
        try:
            pygame.mixer.music.play(loops=-1, fade_ms=fade_ms)
        except pygame.error:
            self.music_available = False
            return
        self.music_started = True
        self.music_paused = False

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not self.music_available:
            return
        try:
            if enabled:
                if self.music_paused:
                    pygame.mixer.music.unpause()
                    self.music_paused = False
                elif not self.music_started:
                    self._start_music()
            elif self.music_started and not self.music_paused:
                pygame.mixer.music.pause()
                self.music_paused = True
        except pygame.error:
            pass

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, volume))
        for sound in self.sounds.values():
            sound.set_volume(self.volume)
        if self.music_available:
            try:
                pygame.mixer.music.set_volume(self.volume * MUSIC_GAIN)
            except pygame.error:
                pass

    def play(self, name: str) -> None:
        if not (self.available and self.enabled):
            return
        sound = self.sounds.get(name)
        if sound is None:
            return
        try:
            sound.play()
        except pygame.error:
            pass
