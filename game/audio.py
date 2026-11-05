"""Procedurally generated sound effects.

The game ships no audio files: every cue is synthesised at start-up from simple
waveforms, which keeps the package tiny and fully offline.  Sound can be muted
from the settings screen; a missing audio device is tolerated silently.
"""

from __future__ import annotations

import math
import random
from array import array
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pygame

SAMPLE_RATE = 44100


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
    rng = random.Random(11)
    cues: Dict[str, bytes] = {}

    cues["click"] = _to_bytes(_tone(880, 0.055, 0.25, 0.2))
    cues["hover"] = _to_bytes(_tone(1320, 0.03, 0.08, 0.1))

    place = _tone(320, 0.08, 0.3, 0.6)
    for index in range(len(place)):
        place[index] *= 1.0 - 0.7 * (index / len(place))
    cues["place"] = _to_bytes(place)
    cues["undo"] = _to_bytes(_tone(420, 0.07, 0.22, 0.4))

    cues["start"] = _to_bytes(_mix_sequence([_tone(523, 0.09, 0.3), _tone(784, 0.12, 0.3)], 0.01))
    cues["step"] = _to_bytes(_tone(660, 0.035, 0.10, 0.1))
    cues["paused"] = _to_bytes(_tone(392, 0.08, 0.18, 0.2))

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

    # a light "flap" built from filtered noise
    noise = [rng.uniform(-0.35, 0.35) * (1 - i / 1800) for i in range(1800)]
    cues["flap"] = _to_bytes(noise)
    return cues


class AudioManager:
    """Tiny wrapper around ``pygame.mixer`` with graceful degradation."""

    def __init__(self, enabled: bool = True, volume: float = 0.6) -> None:
        self.enabled = enabled
        self.volume = volume
        self.available = False
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
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
                sound.set_volume(volume)
                self.sounds[name] = sound
        except (pygame.error, ValueError):
            self.available = False

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, volume))
        for sound in self.sounds.values():
            sound.set_volume(self.volume)

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
