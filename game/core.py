"""Pure grid-chase simulation.

Everything in this module is head-less: no pygame import, no file access, no
randomness.  The renderer and the user interface only ever read from it, which
keeps the rule set trivially unit testable.

Rule summary
------------
* The farmer and every cow move on the same tick.  Both next states are
  computed from the *current* state and only then committed, so no actor can
  react to a move that happens during the same tick.
* An actor walks one tile forward when that tile is walkable.  Otherwise it
  turns 90 degrees clockwise and stays where it is for that tick.
* Actors never block each other; only fences, trees, ponds, hedges, board edges
  and player-placed obstacles do.
* Catching a cow wins immediately, even when the resulting state was seen
  before (the game ends before the loop check).
* Repeating a full state (farmer pose + every cow pose + obstacle layout) is a
  time loop and loses.
* Running out of the step budget loses.
"""

from __future__ import annotations

from typing import Callable, Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

from .models import (
    Actor,
    ActorTick,
    Cow,
    CowPersonality,
    Direction,
    GameStatus,
    Level,
    PlacementResult,
    Pos,
    PredictionFrame,
    StateKey,
    TickResult,
)

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


def advance_actor(
    actor: Actor,
    blocked: Callable[[Pos], bool],
    personality: CowPersonality = CowPersonality.NORMAL,
) -> ActorTick:
    """Compute the next state of one actor without mutating anything."""
    target = step_forward(actor.pos, actor.facing)
    if not blocked(target):
        return ActorTick(actor.pos, target, actor.facing, actor.facing, True)
    if personality is CowPersonality.STUBBORN:
        turned = actor.facing.counter_clockwise()
    else:
        turned = actor.facing.clockwise()
    return ActorTick(actor.pos, actor.pos, actor.facing, turned, False)


class Simulation:
    """Mutable, deterministic game state for one attempt at one level."""

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
            illegal = [p for p in self._obstacles if not self._obstacle_tile_ok(p)]
            for pos in illegal:
                self._obstacles.discard(pos)
        self.farmer = Actor(level.farmer_start, level.farmer_facing)
        personalities = list(level.cow_personalities) or [CowPersonality.NORMAL] * len(
            level.cow_positions
        )
        if len(personalities) < len(level.cow_positions):
            personalities += [CowPersonality.NORMAL] * (
                len(level.cow_positions) - len(personalities)
            )
        self.cows: Tuple[Cow, ...] = tuple(
            Cow(pos, facing, personalities[i])
            for i, (pos, facing) in enumerate(zip(level.cow_positions, level.cow_facings))
        )
        self.steps = 0
        self.status = GameStatus.READY
        self.last_tick: Optional[TickResult] = None
        self._history: List[StateKey] = [self.state_key()]

    # ------------------------------------------------------------------
    # Obstacles
    # ------------------------------------------------------------------
    @property
    def obstacles(self) -> FrozenSet[Pos]:
        return frozenset(self._obstacles)

    @property
    def obstacle_count(self) -> int:
        return len(self._obstacles)

    @property
    def obstacles_left(self) -> int:
        return max(0, self.level.obstacle_limit - len(self._obstacles))

    def _obstacle_tile_ok(self, pos: Pos) -> bool:
        if not self.board.inside(pos):
            return False
        if self.board.is_wall(pos):
            return False
        if pos == self.level.farmer_start:
            return False
        if pos in self.level.cow_positions:
            return False
        if pos in self.level.apple_positions:
            return False
        return True

    def can_place_obstacle(self, pos: Pos) -> PlacementResult:
        if self.status is not GameStatus.READY:
            return PlacementResult(False, "游戏开始后不能再放置障碍")
        if not self.board.inside(pos):
            return PlacementResult(False, "不能在牧场外面放置障碍")
        if self.board.is_wall(pos):
            return PlacementResult(False, "这里已经有围栏或树木了")
        if pos in self._obstacles:
            return PlacementResult(False, "这里已经有一块石头了")
        if pos == self.level.farmer_start:
            return PlacementResult(False, "不能挡在农夫脚下")
        if pos in self.level.cow_positions:
            return PlacementResult(False, "不能挡在牛的脚下")
        if pos in self.level.apple_positions:
            return PlacementResult(False, "苹果上不能放障碍")
        if len(self._obstacles) >= self.level.obstacle_limit:
            return PlacementResult(False, "障碍已经用完了")
        return PlacementResult(True, "")

    def place_obstacle(self, pos: Pos) -> PlacementResult:
        result = self.can_place_obstacle(pos)
        if not result.ok:
            return result
        self._obstacles.add(pos)
        self._history = [self.state_key()]
        return PlacementResult(True, "")

    def remove_obstacle(self, pos: Pos) -> bool:
        if self.status is not GameStatus.READY:
            return False
        if pos not in self._obstacles:
            return False
        self._obstacles.discard(pos)
        self._history = [self.state_key()]
        return True

    def clear_obstacles(self) -> None:
        if self.status is not GameStatus.READY:
            return
        self._obstacles.clear()
        self._history = [self.state_key()]

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------
    def blocked(self, pos: Pos) -> bool:
        """True when an actor cannot walk into ``pos``."""
        return not self.board.walkable(pos) or pos in self._obstacles

    def state_key(self) -> StateKey:
        farmer = (self.farmer.pos[0], self.farmer.pos[1], int(self.farmer.facing))
        cows = tuple(
            (cow.pos[0], cow.pos[1], int(cow.facing)) for cow in self.cows
        )
        return (farmer, cows, frozenset(self._obstacles))

    @property
    def caught(self) -> bool:
        return any(cow.pos == self.farmer.pos for cow in self.cows)

    def start(self) -> None:
        if self.status is GameStatus.READY:
            self.status = GameStatus.PLAYING

    def step(self) -> Optional[TickResult]:
        """Advance exactly one synchronous tick.

        Returns ``None`` when the game is not running any more.
        """
        if self.status is GameStatus.READY:
            self.status = GameStatus.PLAYING
        if self.status is not GameStatus.PLAYING:
            return None

        farmer_tick = advance_actor(self.farmer, self.blocked)
        cow_ticks = tuple(
            advance_actor(cow, self.blocked, cow.personality) for cow in self.cows
        )

        # Commit every actor at once: the rule is synchronous by definition.
        self.farmer = Actor(farmer_tick.end_pos, farmer_tick.end_facing)
        self.cows = tuple(
            Cow(tick.end_pos, tick.end_facing, cow.personality)
            for cow, tick in zip(self.cows, cow_ticks)
        )
        self.steps += 1

        caught = self.caught
        loop_hit = False
        key = self.state_key()

        if caught:
            self.status = GameStatus.WON
        elif key in self._history:
            loop_hit = True
            self.status = GameStatus.LOST_LOOP
        elif self.steps >= self.level.step_limit:
            self.status = GameStatus.LOST_STEPS
        else:
            self._history.append(key)

        result = TickResult(
            farmer=farmer_tick,
            cows=cow_ticks,
            status=self.status,
            steps=self.steps,
            caught=caught,
            loop_hit=loop_hit,
        )
        self.last_tick = result
        return result

    # ------------------------------------------------------------------
    # Forecasting
    # ------------------------------------------------------------------
    def predict(self, count: int = 3) -> List[PredictionFrame]:
        """Project the next ``count`` ticks without touching the live state."""
        frames: List[PredictionFrame] = []
        farmer_pos = self.farmer.pos
        farmer_facing = self.farmer.facing
        cows = [(cow.pos, cow.facing, cow.personality) for cow in self.cows]
        steps = self.steps
        history = set(self._history)
        status = GameStatus.PLAYING if self.status is GameStatus.PLAYING else self.status

        if status.is_finished:
            return frames

        for index in range(1, count + 1):
            farmer_tick = advance_actor(Actor(farmer_pos, farmer_facing), self.blocked)
            cow_ticks = [
                advance_actor(Actor(pos, facing), self.blocked, personality)
                for pos, facing, personality in cows
            ]
            farmer_pos, farmer_facing = farmer_tick.end_pos, farmer_tick.end_facing
            cows = [
                (tick.end_pos, tick.end_facing, personality)
                for tick, (_, _, personality) in zip(cow_ticks, cows)
            ]
            steps += 1
            caught = any(pos == farmer_pos for pos, _, _ in cows)
            key: StateKey = (
                (farmer_pos[0], farmer_pos[1], int(farmer_facing)),
                tuple((p[0], p[1], int(f)) for p, f, _ in cows),
                frozenset(self._obstacles),
            )
            if caught:
                projected = GameStatus.WON
            elif key in history:
                projected = GameStatus.LOST_LOOP
            elif steps >= self.level.step_limit:
                projected = GameStatus.LOST_STEPS
            else:
                projected = GameStatus.PLAYING
            history.add(key)
            frames.append(
                PredictionFrame(
                    step=index,
                    farmer_pos=farmer_pos,
                    farmer_facing=farmer_facing,
                    cow_positions=tuple(p for p, _, _ in cows),
                    cow_facings=tuple(f for _, f, _ in cows),
                    status=projected,
                )
            )
            if projected.is_finished:
                break
        return frames

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    @property
    def rank(self):
        return self.level.rank_for(self.steps)

    def reset(self) -> None:
        """Restart the attempt, keeping the player's obstacle layout."""
        obstacles = set(self._obstacles)
        self.__init__(self.level, obstacles, validate=False)

    def snapshot(self) -> Dict[str, object]:
        """Small, JSON friendly view used by the interface."""
        return {
            "steps": self.steps,
            "status": self.status.value,
            "obstacles": sorted([list(p) for p in self._obstacles]),
            "farmer": [list(self.farmer.pos), int(self.farmer.facing)],
            "cows": [
                [list(cow.pos), int(cow.facing), cow.personality.value]
                for cow in self.cows
            ],
        }
