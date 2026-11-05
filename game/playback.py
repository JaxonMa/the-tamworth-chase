"""Real-time playback controller.

Keeps the pure simulation in sync with the animation clock without letting the
renderer touch the rules.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from .core import Simulation
from .models import ActorTick, Direction, GameStatus, TickResult

BASE_INTERVAL = 0.62
ANIM_FRACTION = 0.55


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


class Playback:
    """Drives the simulation clock."""

    def __init__(self, sim: Simulation, speed: float = 1.0) -> None:
        self.sim = sim
        self.speed = speed
        self.running = False
        self.finished = False
        self.age = 0.0
        self.last_tick: Optional[TickResult] = None
        self.total_time = 0.0
        self.slow_motion = 1.0

    # ------------------------------------------------------------------
    def interval(self) -> float:
        speed = max(0.1, self.speed)
        return BASE_INTERVAL / speed * (1.0 / self.slow_motion)

    def anim_duration(self) -> float:
        return self.interval() * ANIM_FRACTION

    def start(self) -> None:
        if self.sim.status is GameStatus.READY:
            self.sim.start()
        if not self.finished:
            self.running = True
            self.age = self.interval()

    def pause(self) -> None:
        self.running = False

    def toggle_pause(self) -> None:
        if self.finished:
            return
        self.running = not self.running

    def set_speed(self, speed: float) -> None:
        self.speed = speed

    def step_once(self) -> Optional[TickResult]:
        if self.finished:
            return None
        self.running = False
        tick = self.sim.step()
        self._register(tick)
        self.age = 0.0
        return tick

    def _register(self, tick: Optional[TickResult]) -> None:
        if tick is None:
            return
        self.last_tick = tick
        self.age = 0.0
        if tick.status.is_finished:
            self.running = False
            self.finished = True

    def update(self, dt: float) -> bool:
        """Advance the clock.  Returns True when a new tick was executed."""
        self.total_time += dt
        if not self.running or self.finished:
            return False
        self.age += dt
        interval = self.interval()
        stepped = False
        guard = 0
        while self.age >= interval and not self.finished and guard < 4:
            guard += 1
            self.age -= interval
            tick = self.sim.step()
            self._register(tick)
            stepped = True
            if tick is None or tick.status.is_finished:
                break
        return stepped

    # ------------------------------------------------------------------
    @property
    def anim_progress(self) -> float:
        duration = self.anim_duration()
        if duration <= 0:
            return 1.0
        return max(0.0, min(1.0, self.age / duration))

    def actor_visuals(self) -> Tuple[VisualActor, Tuple[VisualActor, ...]]:
        """Return interpolated positions for the farmer and every cow."""
        sim = self.sim
        tick = self.last_tick
        progress = self.anim_progress
        active = tick is not None and progress < 1.0 and not self.finished

        def make(tick_data: Optional[ActorTick], pos, facing: Direction) -> VisualActor:
            if not active or tick_data is None:
                return VisualActor(float(pos[0]), float(pos[1]), facing, False, 0.0, False)
            eased = _ease_out_cubic(progress)
            row = _lerp(tick_data.start_pos[0], tick_data.end_pos[0], eased)
            col = _lerp(tick_data.start_pos[1], tick_data.end_pos[1], eased)
            turning = tick_data.turned
            display_facing = tick_data.end_facing if progress >= 0.45 else tick_data.start_facing
            wobble = 0.0
            if turning:
                delta = (int(tick_data.end_facing) - int(tick_data.start_facing)) % 4
                direction_sign = 1.0 if delta == 3 else -1.0
                wobble = direction_sign * 7.0 * math.sin(math.pi * progress)
            return VisualActor(
                row=row,
                col=col,
                facing=display_facing,
                turning=turning,
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
