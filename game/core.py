"""Pure turn-based chase-and-escape simulation.

Everything in this module is head-less: no pygame import, no file access, no
randomness.  Farmer John drives like a tank while the cows try to reach an exit.
The renderer and the user interface only read from it, which keeps the rule set
trivially unit testable.

Rule summary
------------
* The player turns the farmer to an absolute direction or moves forward.
* A same-direction turn is invalid and does not consume the turn.
* A blocked forward move still consumes the turn.
* The farmer catches a cow by entering its tile.
* Cows move after the farmer, in fixed order.  A cow that can see the farmer
  flees; otherwise it seeks the nearest exit it can see or patrols.
* All cows must be caught to win.  Any cow reaching an exit loses immediately.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

from .models import (
    Action,
    Actor,
    ActorTick,
    Cow,
    Direction,
    GameStatus,
    Level,
    Pos,
    PredictionFrame,
    Rank,
    StateKey,
    TickResult,
    TieBreak,
)


def step_forward(pos: Pos, facing: Direction) -> Pos:
    dr, dc = facing.delta
    return (pos[0] + dr, pos[1] + dc)


def manhattan(a: Pos, b: Pos) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def direction_between(a: Pos, b: Pos) -> Optional[Direction]:
    """Return the cardinal direction from ``a`` to ``b`` or ``None``."""
    if a[0] == b[0] and a[1] != b[1]:
        return Direction.EAST if b[1] > a[1] else Direction.WEST
    if a[1] == b[1] and a[0] != b[0]:
        return Direction.SOUTH if b[0] > a[0] else Direction.NORTH
    return None


def _turned(facing: Direction, tie: TieBreak) -> Direction:
    return facing.counter_clockwise() if tie is TieBreak.LEFT else facing.clockwise()


class Board:
    """Static terrain for a level."""

    def __init__(self, level: Level) -> None:
        self.level = level
        self.width = level.width
        self.height = level.height
        self.walls: FrozenSet[Pos] = level.wall_positions
        self.obstacles: FrozenSet[Pos] = frozenset(level.obstacles)

    def inside(self, pos: Pos) -> bool:
        return 0 <= pos[0] < self.height and 0 <= pos[1] < self.width

    def is_wall(self, pos: Pos) -> bool:
        return pos in self.walls

    def walkable(self, pos: Pos) -> bool:
        return self.inside(pos) and pos not in self.walls and pos not in self.obstacles

    def neighbours(self, pos: Pos) -> Iterable[Pos]:
        for direction in Direction:
            candidate = step_forward(pos, direction)
            if self.walkable(candidate):
                yield candidate


@dataclass(frozen=True)
class _Snapshot:
    farmer: Actor
    cows: Tuple[Cow, ...]
    caught: Tuple[bool, ...]
    turns: int
    status: GameStatus
    last_tick: Optional[TickResult]
    seen: FrozenSet[StateKey]
    loop_events: int
    loop_hint_last: bool
    blocked_events: int


class Simulation:
    """Mutable, deterministic game state for one attempt at one level."""

    MAX_HISTORY = 256

    def __init__(self, level: Level) -> None:
        self.level = level
        self.board = Board(level)
        self.farmer = Actor(level.farmer_start, level.farmer_facing)
        self.cows: Tuple[Cow, ...] = tuple(
            Cow(pos, facing)
            for pos, facing in zip(level.cow_positions, level.cow_facings)
        )
        self.caught: Tuple[bool, ...] = (False,) * len(self.cows)
        self._exit_cells: FrozenSet[Pos] = frozenset(level.exit_cells)
        self.turns = 0
        self.status = GameStatus.PLAYING
        self.last_tick: Optional[TickResult] = None
        self.loop_events = 0
        self.loop_hint_last = False
        self.blocked_events = 0
        self._seen: Set[StateKey] = {self.state_key()}
        self._undo: List[_Snapshot] = []
        self._redo: List[_Snapshot] = []

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    @property
    def exit_cells(self) -> FrozenSet[Pos]:
        return self._exit_cells

    @property
    def obstacles(self) -> FrozenSet[Pos]:
        return frozenset(self.level.obstacles)

    @property
    def caught_count(self) -> int:
        return sum(1 for flag in self.caught if flag)

    @property
    def all_caught(self) -> bool:
        return bool(self.cows) and all(self.caught)

    @property
    def active_indices(self) -> Iterable[int]:
        return (index for index, flag in enumerate(self.caught) if not flag)

    @property
    def active_cows(self) -> Tuple[Cow, ...]:
        return tuple(cow for cow, flag in zip(self.cows, self.caught) if not flag)

    def walkable_for_farmer(self, pos: Pos) -> bool:
        return self.board.walkable(pos)

    def blocked(self, pos: Pos) -> bool:
        return not self.board.walkable(pos)

    # ------------------------------------------------------------------
    # Lines of sight
    # ------------------------------------------------------------------
    def _line_clear(
        self,
        start: Pos,
        end: Pos,
        *,
        extra_blockers: Iterable[Pos] = (),
    ) -> bool:
        """Whether the straight horizontal/vertical segment is unobstructed."""
        if start[0] != end[0] and start[1] != end[1]:
            return False
        dr = (end[0] > start[0]) - (end[0] < start[0])
        dc = (end[1] > start[1]) - (end[1] < start[1])
        row, col = start[0] + dr, start[1] + dc
        blockers = self.board.walls | self.board.obstacles | frozenset(extra_blockers)
        while (row, col) != end:
            if (row, col) in blockers:
                return False
            row += dr
            col += dc
        return True

    def _fj_visible(self, cow: Cow, index: int) -> bool:
        if self.caught[index]:
            return False
        distance = manhattan(cow.pos, self.farmer.pos)
        if distance == 0:
            return True
        if self.level.sight_range >= 0 and distance > self.level.sight_range:
            return False
        blockers: Tuple[Pos, ...] = ()
        if self.level.cows_block_sight:
            blockers = tuple(
                other.pos
                for other_index, (other, flag) in enumerate(zip(self.cows, self.caught))
                if not flag and other_index != index
            )
        return self._line_clear(cow.pos, self.farmer.pos, extra_blockers=blockers)

    def _visible_exit(self, cow: Cow) -> Optional[Pos]:
        best: Optional[Tuple[int, int, int]] = None
        for exit_pos in self._exit_cells:
            if exit_pos[0] != cow.pos[0] and exit_pos[1] != cow.pos[1]:
                continue
            distance = manhattan(cow.pos, exit_pos)
            if self.level.exit_sight_range >= 0 and distance > self.level.exit_sight_range:
                continue
            if not self._line_clear(cow.pos, exit_pos):
                continue
            key = (distance, exit_pos[0], exit_pos[1])
            if best is None or key < best:
                best = key
        if best is None:
            return None
        return (best[1], best[2])

    def cow_is_fleeing(self, index: int) -> bool:
        if index >= len(self.cows) or self.caught[index]:
            return False
        return self._fj_visible(self.cows[index], index)

    def near_exit(self, distance: int = 3) -> Tuple[Pos, ...]:
        """Exit cells with an active cow within ``distance`` (UI highlight)."""
        cells: List[Pos] = []
        for exit_pos in self._exit_cells:
            if any(
                manhattan(cow.pos, exit_pos) <= distance
                for cow, flag in zip(self.cows, self.caught)
                if not flag
            ):
                cells.append(exit_pos)
        return tuple(cells)

    # ------------------------------------------------------------------
    # Cow decisions
    # ------------------------------------------------------------------
    def _cow_can_enter(self, index: int, pos: Pos, cows: Sequence[Cow]) -> bool:
        if not self.board.walkable(pos):
            return False
        if self.level.cows_block_each_other:
            for other_index, cow in enumerate(cows):
                if other_index != index and not self.caught[other_index] and cow.pos == pos:
                    return False
        return True

    def _flee_tick(self, index: int, cow: Cow, cows: Sequence[Cow]) -> ActorTick:
        distance = manhattan(cow.pos, self.farmer.pos)
        target = step_forward(cow.pos, cow.facing)
        if self._cow_can_enter(index, target, cows) and manhattan(target, self.farmer.pos) > distance:
            return ActorTick(cow.pos, target, cow.facing, cow.facing, True)

        left = cow.facing.counter_clockwise()
        right = cow.facing.clockwise()
        left_cell = step_forward(cow.pos, left)
        right_cell = step_forward(cow.pos, right)
        left_distance = manhattan(left_cell, self.farmer.pos)
        right_distance = manhattan(right_cell, self.farmer.pos)
        if left_distance == right_distance:
            chosen = self.level.flee_tiebreak
        else:
            chosen = TieBreak.LEFT if left_distance > right_distance else TieBreak.RIGHT
        facing = left if chosen is TieBreak.LEFT else right
        return ActorTick(cow.pos, cow.pos, cow.facing, facing, False)

    def _patrol_tick(self, index: int, cow: Cow, cows: Sequence[Cow]) -> ActorTick:
        target = step_forward(cow.pos, cow.facing)
        if self._cow_can_enter(index, target, cows):
            return ActorTick(cow.pos, target, cow.facing, cow.facing, True)
        return ActorTick(cow.pos, cow.pos, cow.facing, cow.facing.clockwise(), False)

    def _seek_exit_tick(self, index: int, cow: Cow, cows: Sequence[Cow]) -> ActorTick:
        exit_pos = self._visible_exit(cow)
        if exit_pos is None:
            return self._patrol_tick(index, cow, cows)
        if exit_pos == cow.pos:
            # Defensive only: a level should never start a cow on an exit.
            return self._patrol_tick(index, cow, cows)
        wanted = direction_between(cow.pos, exit_pos)
        if wanted is None:
            return self._patrol_tick(index, cow, cows)
        if cow.facing is wanted:
            target = step_forward(cow.pos, cow.facing)
            if self._cow_can_enter(index, target, cows):
                return ActorTick(cow.pos, target, cow.facing, cow.facing, True)
            chosen = self.level.exit_tiebreak
            facing = _turned(cow.facing, chosen)
            return ActorTick(cow.pos, cow.pos, cow.facing, facing, False)
        if wanted is cow.facing.opposite():
            chosen = self.level.exit_tiebreak
            facing = _turned(cow.facing, chosen)
        elif wanted is cow.facing.counter_clockwise():
            facing = cow.facing.counter_clockwise()
        else:
            facing = cow.facing.clockwise()
        return ActorTick(cow.pos, cow.pos, cow.facing, facing, False)

    def _cow_tick(self, index: int, cows: Sequence[Cow]) -> ActorTick:
        cow = cows[index]
        if self._fj_visible(cow, index):
            return self._flee_tick(index, cow, cows)
        return self._seek_exit_tick(index, cow, cows)

    # ------------------------------------------------------------------
    # Turns
    # ------------------------------------------------------------------
    def _finish_tick(
        self,
        farmer_tick: ActorTick,
        cow_ticks: Tuple[ActorTick, ...],
        *,
        blocked: bool,
        message: str,
        caught_now: Sequence[int],
        escaped_index: Optional[int],
    ) -> TickResult:
        result = TickResult(
            farmer=farmer_tick,
            cows=cow_ticks,
            status=self.status,
            turns=self.turns,
            caught=self.caught,
            caught_now=tuple(caught_now),
            escaped_index=escaped_index,
            loop_hint=self.loop_hint_last,
            blocked=blocked,
            message=message,
        )
        self.last_tick = result
        return result

    def _move_cows(self) -> Tuple[Optional[int], Tuple[int, ...], Tuple[ActorTick, ...]]:
        """Move every active cow once and resolve exits and catches."""
        cow_ticks: List[ActorTick] = [
            ActorTick(cow.pos, cow.pos, cow.facing, cow.facing, False) for cow in self.cows
        ]
        new_cows: List[Cow] = list(self.cows)
        caught_now: List[int] = []
        escaped_index: Optional[int] = None
        for index, cow in enumerate(self.cows):
            if self.caught[index]:
                continue
            tick = self._cow_tick(index, new_cows)
            new_cows[index] = Cow(tick.end_pos, tick.end_facing)
            cow_ticks[index] = tick
            if tick.end_pos in self._exit_cells:
                escaped_index = index
                self.status = GameStatus.LOST_EXIT
                break
            if tick.end_pos == self.farmer.pos:
                self.caught = _set_flag(self.caught, index)
                caught_now.append(index)
        self.cows = tuple(new_cows)
        return escaped_index, tuple(caught_now), tuple(cow_ticks)

    def apply_action(self, action: Action) -> TickResult:
        """Execute one command, then move every cow."""
        if not isinstance(action, Action):
            action = Action(action)
        if self.status is not GameStatus.PLAYING:
            tick = ActorTick(
                self.farmer.pos, self.farmer.pos, self.farmer.facing, self.farmer.facing, False
            )
            return TickResult(
                farmer=tick,
                cows=(),
                status=self.status,
                turns=self.turns,
                caught=self.caught,
                blocked=True,
                message="本局已经结束。",
            )

        if action is not Action.FORWARD and action.direction is self.farmer.facing:
            tick = ActorTick(
                self.farmer.pos, self.farmer.pos, self.farmer.facing, self.farmer.facing, False
            )
            return TickResult(
                farmer=tick,
                cows=(),
                status=self.status,
                turns=self.turns,
                caught=self.caught,
                invalid=True,
                message="已朝该方向",
            )

        self._push_undo()
        caught_now: List[int] = []
        blocked = False
        message = ""
        start = self.farmer

        if action is not Action.FORWARD:
            facing = action.direction
            farmer_tick = ActorTick(start.pos, start.pos, start.facing, facing, False)
            self.farmer = Actor(start.pos, facing)
        else:
            target = step_forward(start.pos, start.facing)
            if not self.board.walkable(target):
                blocked = True
                message = "前方受阻，本回合已消耗"
                self.blocked_events += 1
                farmer_tick = ActorTick(start.pos, start.pos, start.facing, start.facing, False)
            else:
                farmer_tick = ActorTick(start.pos, target, start.facing, start.facing, True)
                self.farmer = Actor(target, start.facing)
                for index, cow in enumerate(self.cows):
                    if not self.caught[index] and cow.pos == target:
                        self.caught = _set_flag(self.caught, index)
                        caught_now.append(index)

        if self.all_caught:
            self.turns += 1
            self.status = GameStatus.WON
            self.loop_hint_last = False
            return self._finish_tick(
                farmer_tick, (), blocked=blocked, message=message,
                caught_now=caught_now, escaped_index=None,
            )

        escaped_index, cow_catches, cow_ticks = self._move_cows()
        caught_now.extend(cow_catches)

        self.turns += 1
        self.loop_hint_last = False
        if self.status is GameStatus.PLAYING:
            if self.all_caught:
                self.status = GameStatus.WON
            elif self.turns >= self.level.max_turns:
                self.status = GameStatus.LOST_TURNS
            else:
                key = self.state_key()
                if key in self._seen:
                    self.loop_hint_last = True
                    self.loop_events += 1
                else:
                    self._seen.add(key)

        return self._finish_tick(
            farmer_tick,
            cow_ticks,
            blocked=blocked,
            message=message,
            caught_now=caught_now,
            escaped_index=escaped_index,
        )

    # ------------------------------------------------------------------
    # Undo / redo
    # ------------------------------------------------------------------
    def _snapshot(self) -> _Snapshot:
        return _Snapshot(
            farmer=self.farmer,
            cows=self.cows,
            caught=self.caught,
            turns=self.turns,
            status=self.status,
            last_tick=self.last_tick,
            seen=frozenset(self._seen),
            loop_events=self.loop_events,
            loop_hint_last=self.loop_hint_last,
            blocked_events=self.blocked_events,
        )

    def _push_undo(self) -> None:
        self._undo.append(self._snapshot())
        if len(self._undo) > self.MAX_HISTORY:
            del self._undo[0]
        self._redo.clear()

    def _restore(self, snapshot: _Snapshot) -> None:
        self.farmer = snapshot.farmer
        self.cows = snapshot.cows
        self.caught = snapshot.caught
        self.turns = snapshot.turns
        self.status = snapshot.status
        self.last_tick = snapshot.last_tick
        self._seen = set(snapshot.seen)
        self.loop_events = snapshot.loop_events
        self.loop_hint_last = snapshot.loop_hint_last
        self.blocked_events = snapshot.blocked_events

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
        changed = False
        while self._undo and self.turns > turn:
            if not self.undo():
                break
            changed = True
        return changed

    # ------------------------------------------------------------------
    # State and forecasting
    # ------------------------------------------------------------------
    def state_key(self) -> StateKey:
        farmer = (self.farmer.pos[0], self.farmer.pos[1], int(self.farmer.facing))
        cows = tuple(
            (cow.pos[0], cow.pos[1], int(cow.facing))
            for cow in self.cows
        )
        return (farmer, cows, self.caught)

    def clone(self) -> "Simulation":
        new = Simulation(self.level)
        new.farmer = self.farmer
        new.cows = self.cows
        new.caught = self.caught
        new.turns = self.turns
        new.status = self.status
        new.last_tick = None
        new.loop_events = self.loop_events
        new.loop_hint_last = self.loop_hint_last
        new.blocked_events = self.blocked_events
        new._seen = set(self._seen)
        return new

    def predict(self, count: Optional[int] = None) -> List[PredictionFrame]:
        """Project the cows' next moves while the farmer stays put."""
        steps = self.level.prediction_steps if count is None else int(count)
        if steps <= 0 or self.status.is_finished:
            return []
        frames: List[PredictionFrame] = []
        probe = self.clone()
        for index in range(1, steps + 1):
            if probe.status.is_finished:
                break
            escaped_index, _, _ = probe._move_cows()
            if probe.status is GameStatus.PLAYING and probe.all_caught:
                probe.status = GameStatus.WON
            frames.append(
                PredictionFrame(
                    step=index,
                    cow_positions=tuple(cow.pos for cow in probe.cows),
                    cow_facings=tuple(cow.facing for cow in probe.cows),
                    caught=probe.caught,
                    status=probe.status,
                    escaped_index=escaped_index,
                )
            )
            if probe.status.is_finished:
                break
        return frames

    @property
    def rank(self) -> Rank:
        return self.level.rank_for(self.turns)

    def reset(self) -> None:
        self.__init__(self.level)

    def snapshot(self) -> dict:
        return {
            "turns": self.turns,
            "status": self.status.value,
            "exits": sorted([list(p) for p in self._exit_cells]),
            "obstacles": sorted([list(p) for p in self.level.obstacles]),
            "farmer": [list(self.farmer.pos), int(self.farmer.facing)],
            "cows": [[list(cow.pos), int(cow.facing)] for cow in self.cows],
            "caught": list(self.caught),
        }


def _set_flag(flags: Tuple[bool, ...], index: int) -> Tuple[bool, ...]:
    values = list(flags)
    values[index] = True
    return tuple(values)
