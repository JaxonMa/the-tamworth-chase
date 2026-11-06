"""Pure turn-based grid chase simulation.

Everything in this module is head-less: no pygame import, no file access, no
randomness.  The renderer and the user interface only ever read from it, which
keeps the rule set trivially unit testable.

Rule summary
------------
* A turn starts with the player ordering the farmer to step one tile in a
  cardinal direction, or to wait in place.
* The farmer cannot enter a wall, a board edge or a hay bale.  A rejected order
  does not consume a turn.
* Moving into a cow wins immediately.
* After the farmer has acted, every cow moves once in fixed index order.  A cow
  walks forward when the next tile is free, otherwise it turns 90 degrees
  clockwise and stays put.
* Moving into the farmer also wins.  In pen levels, having every cow inside a
  pen cell also wins.
* Repeating cow poses is reported as a loop hint; it never loses.
* Running out of the turn budget loses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

from .models import (
    Actor,
    ActorTick,
    Cow,
    Direction,
    GameStatus,
    Level,
    PlacementResult,
    Pos,
    PredictionFrame,
    Rank,
    StateKey,
    TickResult,
)

CowStateKey = Tuple[Tuple[int, int, int], ...]


def step_forward(pos: Pos, facing: Direction) -> Pos:
    """Return the tile directly in front of ``pos``."""
    dr, dc = facing.delta
    return (pos[0] + dr, pos[1] + dc)


class Board:
    """Static terrain for a level.

    The board knows nothing about actors or obstacles; it only answers whether a
    coordinate is inside the meadow and whether its terrain can be walked on.
    """

    def __init__(self, level: Level) -> None:
        self.level = level
        self.width = level.width
        self.height = level.height
        self.walls: FrozenSet[Pos] = level.wall_positions

    def inside(self, pos: Pos) -> bool:
        return 0 <= pos[0] < self.height and 0 <= pos[1] < self.width

    def is_wall(self, pos: Pos) -> bool:
        return pos in self.walls

    def walkable(self, pos: Pos) -> bool:
        return self.inside(pos) and pos not in self.walls

    def neighbours(self, pos: Pos) -> Iterable[Pos]:
        for direction in Direction:
            dr, dc = direction.delta
            candidate = (pos[0] + dr, pos[1] + dc)
            if self.walkable(candidate):
                yield candidate


def advance_actor(actor: Actor, blocked: Callable[[Pos], bool]) -> ActorTick:
    """Compute the next state of one cow without mutating anything.

    Cows walk forward when possible and otherwise turn clockwise in place.
    """
    target = step_forward(actor.pos, actor.facing)
    if not blocked(target):
        return ActorTick(actor.pos, target, actor.facing, actor.facing, True)
    return ActorTick(actor.pos, actor.pos, actor.facing, actor.facing.clockwise(), False)


@dataclass(frozen=True)
class _Snapshot:
    """Everything needed to restore one exact past turn."""

    farmer: Actor
    cows: Tuple[Cow, ...]
    obstacles: FrozenSet[Pos]
    turns: int
    status: GameStatus
    last_tick: Optional[TickResult]
    seen: FrozenSet[CowStateKey]
    loop_events: int
    loop_hint_last: bool


class Simulation:
    """Mutable, deterministic game state for one attempt at one level."""

    MAX_HISTORY = 256

    def __init__(
        self,
        level: Level,
        obstacles: Iterable[Pos] = (),
        *,
        validate: bool = True,
    ) -> None:
        self.level = level
        self.board = Board(level)
        self._obstacles: Set[Pos] = set(obstacles)
        if validate:
            for pos in list(self._obstacles):
                if not self._obstacle_tile_ok(pos):
                    self._obstacles.discard(pos)
        self.farmer = Actor(level.farmer_start, level.farmer_facing)
        self.cows: Tuple[Cow, ...] = tuple(
            Cow(pos, facing) for pos, facing in zip(level.cow_positions, level.cow_facings)
        )
        self._pen_cells: FrozenSet[Pos] = frozenset(level.pen_cells)
        self.turns = 0
        self.status = GameStatus.READY
        self.last_tick: Optional[TickResult] = None
        self.loop_events = 0
        self.loop_hint_last = False
        self._seen: Set[CowStateKey] = {self.cow_state_key()}
        self._undo: List[_Snapshot] = []
        self._redo: List[_Snapshot] = []

    # ------------------------------------------------------------------
    # Placement
    # ------------------------------------------------------------------
    @property
    def obstacles(self) -> FrozenSet[Pos]:
        return frozenset(self._obstacles)

    @property
    def obstacle_count(self) -> int:
        return len(self._obstacles)

    @property
    def obstacles_left(self) -> int:
        return max(0, self.level.initial_obstacles - len(self._obstacles))

    @property
    def pen_cells(self) -> FrozenSet[Pos]:
        return self._pen_cells

    def _obstacle_tile_ok(self, pos: Pos) -> bool:
        if not self.board.inside(pos):
            return False
        if self.board.is_wall(pos):
            return False
        if pos == self.level.farmer_start:
            return False
        if pos in self.level.cow_positions:
            return False
        return True

    def can_place_obstacle(self, pos: Pos) -> PlacementResult:
        if self.status is not GameStatus.READY:
            return PlacementResult(False, "追逐开始后不能再放干草垛")
        if not self.board.inside(pos):
            return PlacementResult(False, "不能在牧场外面放干草垛")
        if self.board.is_wall(pos):
            return PlacementResult(False, "这里已经有围栏或树木了")
        if pos in self._obstacles:
            return PlacementResult(False, "这里已经有一垛干草了")
        if pos == self.level.farmer_start:
            return PlacementResult(False, "不能挡在农夫脚下")
        if pos in self.level.cow_positions:
            return PlacementResult(False, "不能挡在牛的脚下")
        if len(self._obstacles) >= self.level.initial_obstacles:
            return PlacementResult(False, "干草垛已经用完了")
        return PlacementResult(True, "")

    def place_obstacle(self, pos: Pos) -> PlacementResult:
        result = self.can_place_obstacle(pos)
        if not result.ok:
            return result
        self._push_undo()
        self._obstacles.add(pos)
        return PlacementResult(True, "")

    def remove_obstacle(self, pos: Pos) -> bool:
        if self.status is not GameStatus.READY:
            return False
        if pos not in self._obstacles:
            return False
        self._push_undo()
        self._obstacles.discard(pos)
        return True

    def clear_obstacles(self) -> None:
        if self.status is not GameStatus.READY:
            return
        if not self._obstacles:
            return
        self._push_undo()
        self._obstacles.clear()

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------
    def blocked(self, pos: Pos) -> bool:
        """True when a cow cannot walk into ``pos``."""
        if not self.board.walkable(pos):
            return True
        return pos in self._obstacles

    def walkable_for_farmer(self, pos: Pos) -> bool:
        """The farmer may share a cow tile: stepping there catches it."""
        return self.board.walkable(pos) and pos not in self._obstacles

    def _cow_blocked(self, index: int, cows: Sequence[Cow]) -> Callable[[Pos], bool]:
        def test(pos: Pos) -> bool:
            if self.blocked(pos):
                return True
            if self.level.cows_block_each_other:
                for other_index, cow in enumerate(cows):
                    if other_index != index and cow.pos == pos:
                        return True
            return False

        return test

    def cow_state_key(self) -> CowStateKey:
        return tuple((cow.pos[0], cow.pos[1], int(cow.facing)) for cow in self.cows)

    def state_key(self) -> StateKey:
        farmer = (self.farmer.pos[0], self.farmer.pos[1], int(self.farmer.facing))
        return (
            farmer,
            self.cow_state_key(),
            frozenset(self._obstacles),
            self.turns,
            self.status.value,
        )

    @property
    def caught(self) -> bool:
        return any(cow.pos == self.farmer.pos for cow in self.cows)

    @property
    def penned_count(self) -> int:
        return sum(1 for cow in self.cows if cow.pos in self._pen_cells)

    @property
    def all_penned(self) -> bool:
        return bool(self.cows) and all(cow.pos in self._pen_cells for cow in self.cows)

    def win_reached(self) -> Tuple[bool, bool]:
        """Return ``(caught, penned)`` for the current position."""
        caught = self.caught
        penned = self.level.is_pen_level and self.all_penned
        return caught, penned

    def start(self) -> None:
        if self.status is not GameStatus.READY:
            return
        self._push_undo()
        self.status = GameStatus.PLAYING
        self._seen = {self.cow_state_key()}

    def order(self, direction: Optional[Direction]) -> TickResult:
        """Carry out one player turn: farmer first, then every cow.

        ``None`` waits in place.  An illegal farmer move is rejected without
        consuming a turn and without moving any cow.
        """
        if self.status is not GameStatus.PLAYING:
            return self._rejected("现在还不能行动。")

        target = self.farmer.pos if direction is None else step_forward(self.farmer.pos, direction)
        if direction is not None and not self.walkable_for_farmer(target):
            return self._rejected("前面过不去，这一下不算回合。")

        self._push_undo()
        start = self.farmer
        if direction is None:
            farmer_tick = ActorTick(start.pos, start.pos, start.facing, start.facing, False)
        else:
            farmer_tick = ActorTick(start.pos, target, start.facing, direction, True)
            self.farmer = Actor(target, direction)

        caught, penned = self.win_reached()
        if caught or penned:
            self.turns += 1
            self.status = GameStatus.WON
            result = TickResult(
                farmer=farmer_tick,
                cows=(),
                status=self.status,
                turns=self.turns,
                caught=caught,
                penned=penned,
            )
            self.last_tick = result
            return result

        # Cows move in fixed list order; earlier cows are committed before the
        # next cow is considered, which makes the order observable and testable.
        cow_ticks: List[ActorTick] = []
        new_cows: List[Cow] = list(self.cows)
        for index, cow in enumerate(self.cows):
            tick = advance_actor(cow, self._cow_blocked(index, new_cows))
            new_cows[index] = Cow(tick.end_pos, tick.end_facing)
            cow_ticks.append(tick)
        self.cows = tuple(new_cows)

        caught, penned = self.win_reached()
        self.turns += 1
        loop_hint = False
        if caught or penned:
            self.status = GameStatus.WON
        else:
            key = self.cow_state_key()
            if key in self._seen:
                loop_hint = True
                self.loop_events += 1
            else:
                self._seen.add(key)
            if self.turns >= self.level.max_turns:
                self.status = GameStatus.LOST_TURNS
            else:
                self.status = GameStatus.PLAYING

        result = TickResult(
            farmer=farmer_tick,
            cows=tuple(cow_ticks),
            status=self.status,
            turns=self.turns,
            caught=caught,
            penned=penned,
            loop_hint=loop_hint,
        )
        self.last_tick = result
        self.loop_hint_last = loop_hint
        return result

    def wait(self) -> TickResult:
        """Spend one turn without moving the farmer."""
        return self.order(None)

    def _rejected(self, message: str) -> TickResult:
        farmer_tick = ActorTick(
            self.farmer.pos,
            self.farmer.pos,
            self.farmer.facing,
            self.farmer.facing,
            False,
        )
        return TickResult(
            farmer=farmer_tick,
            cows=(),
            status=self.status,
            turns=self.turns,
            blocked=True,
            message=message,
        )

    # ------------------------------------------------------------------
    # Undo / redo
    # ------------------------------------------------------------------
    def _snapshot(self) -> _Snapshot:
        return _Snapshot(
            farmer=self.farmer,
            cows=self.cows,
            obstacles=frozenset(self._obstacles),
            turns=self.turns,
            status=self.status,
            last_tick=self.last_tick,
            seen=frozenset(self._seen),
            loop_events=self.loop_events,
            loop_hint_last=self.loop_hint_last,
        )

    def _push_undo(self) -> None:
        self._undo.append(self._snapshot())
        if len(self._undo) > self.MAX_HISTORY:
            del self._undo[0]
        self._redo.clear()

    def _restore(self, snapshot: _Snapshot) -> None:
        self.farmer = snapshot.farmer
        self.cows = snapshot.cows
        self._obstacles = set(snapshot.obstacles)
        self.turns = snapshot.turns
        self.status = snapshot.status
        self.last_tick = snapshot.last_tick
        self._seen = set(snapshot.seen)
        self.loop_events = snapshot.loop_events
        self.loop_hint_last = snapshot.loop_hint_last

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def history_depth(self) -> int:
        return len(self._undo)

    def undo(self) -> bool:
        """Restore the state before the most recent action."""
        if not self._undo:
            return False
        self._redo.append(self._snapshot())
        self._restore(self._undo.pop())
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self._snapshot())
        self._restore(self._redo.pop())
        return True

    def undo_to_turn(self, turn: int) -> bool:
        """Undo repeatedly until the attempt is at or before ``turn``."""
        changed = False
        while self._undo and self.turns > turn:
            if not self.undo():
                break
            changed = True
        return changed

    # ------------------------------------------------------------------
    # Forecasting
    # ------------------------------------------------------------------
    def clone(self) -> "Simulation":
        """A playable copy used for forecasting without touching live state."""
        new = Simulation(self.level, self._obstacles, validate=False)
        new.farmer = self.farmer
        new.cows = self.cows
        new.turns = self.turns
        new.status = GameStatus.PLAYING
        new.last_tick = None
        new._seen = set(self._seen)
        new.loop_events = self.loop_events
        return new

    def predict(self, count: Optional[int] = None) -> List[PredictionFrame]:
        """Project the cows' next ``count`` moves while the farmer waits."""
        steps = self.level.prediction_steps if count is None else int(count)
        if steps <= 0 or self.status.is_finished:
            return []
        frames: List[PredictionFrame] = []
        probe = self.clone()
        for index in range(1, steps + 1):
            tick = probe.order(None)
            if tick.blocked:
                break
            frames.append(
                PredictionFrame(
                    step=index,
                    cow_positions=tuple(cow.pos for cow in probe.cows),
                    cow_facings=tuple(cow.facing for cow in probe.cows),
                    status=probe.status,
                )
            )
            if probe.status.is_finished:
                break
        return frames

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    @property
    def rank(self) -> Rank:
        return self.level.rank_for(self.turns)

    def reset(self) -> None:
        """Restart the attempt in the placement phase, keeping the layout."""
        obstacles = set(self._obstacles)
        self.__init__(self.level, obstacles, validate=False)

    def snapshot(self) -> dict:
        """Small, JSON friendly view used by the interface and the tools."""
        return {
            "turns": self.turns,
            "status": self.status.value,
            "obstacles": sorted([list(p) for p in self._obstacles]),
            "pen_cells": sorted([list(p) for p in self._pen_cells]),
            "farmer": [list(self.farmer.pos), int(self.farmer.facing)],
            "cows": [[list(cow.pos), int(cow.facing)] for cow in self.cows],
        }
