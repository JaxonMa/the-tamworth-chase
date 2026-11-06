"""One-turn animation helpers.

The simulation is turn based, so there is no clock that steps the rules.  The
interface calls :meth:`TurnAnimator.play` after it has executed a turn, and the
animator only interpolates the visual positions between the recorded start and
end states.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from .models import ActorTick, Direction, TickResult
from .core import Simulation

TURN_DURATION = 0.2


@dataclass
class VisualActor:
    """Interpolated on-screen state of one actor."""

    row: float
    col: float
    facing: Direction
    turning: bool
    wobble: float
    moving: bool


def _ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


class TurnAnimator:
    """Interpolates the farmer and the cows through one completed turn."""

    def __init__(self, duration: float = TURN_DURATION) -> None:
        self.duration = duration
        self.tick: Optional[TickResult] = None
        self.age = 0.0
        self.active = False

    # ------------------------------------------------------------------
    def play(self, tick: Optional[TickResult]) -> None:
        if tick is None or tick.blocked:
            return
        self.tick = tick
        self.age = 0.0
        self.active = True

    def clear(self) -> None:
        self.tick = None
        self.age = 0.0
        self.active = False

    @property
    def busy(self) -> bool:
        return self.active

    def update(self, dt: float) -> None:
        if not self.active:
            return
        self.age += dt
        if self.age >= self.duration:
            self.age = self.duration
            self.active = False

    @property
    def progress(self) -> float:
        if self.duration <= 0:
            return 1.0
        return max(0.0, min(1.0, self.age / self.duration))

    # ------------------------------------------------------------------
    def actor_visuals(self, sim: Simulation) -> Tuple[VisualActor, Tuple[VisualActor, ...]]:
        """Return interpolated positions for the farmer and every cow."""
        tick = self.tick
        progress = self.progress
        active = self.active and tick is not None

        def make(tick_data: Optional[ActorTick], pos, facing: Direction) -> VisualActor:
            if not active or tick_data is None:
                return VisualActor(float(pos[0]), float(pos[1]), facing, False, 0.0, False)
            eased = _ease_out_cubic(progress)
            row = _lerp(tick_data.start_pos[0], tick_data.end_pos[0], eased)
            col = _lerp(tick_data.start_pos[1], tick_data.end_pos[1], eased)
            display_facing = (
                tick_data.end_facing if progress >= 0.45 else tick_data.start_facing
            )
            wobble = 0.0
            if tick_data.turned:
                delta = (int(tick_data.end_facing) - int(tick_data.start_facing)) % 4
                direction_sign = 1.0 if delta == 3 else -1.0
                wobble = direction_sign * 7.0 * math.sin(math.pi * progress)
            return VisualActor(
                row=row,
                col=col,
                facing=display_facing,
                turning=tick_data.turned,
                wobble=wobble,
                moving=tick_data.moved,
            )

        farmer_tick = tick.farmer if tick else None
        farmer = make(farmer_tick, sim.farmer.pos, sim.farmer.facing)
        cows = []
        for index, cow in enumerate(sim.cows):
            cow_tick = tick.cows[index] if tick and index < len(tick.cows) else None
            cows.append(make(cow_tick, cow.pos, cow.facing))
        return farmer, tuple(cows)
