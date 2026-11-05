"""Pure grid-chase simulation.

Everything in this module is head-less: no pygame import, no file access, no
randomness.  The renderer and the user interface only ever read from it, which
keeps the rule set trivially unit testable.

Rule summary
------------
* The farmer and every cow move on the same tick.  All next states are computed
  from the *current* state and only then committed, so no actor can react to a
  move that happens during the same tick.
* An actor walks one tile forward when that tile is walkable.  Otherwise it
  turns 90 degrees clockwise and stays where it is for that tick.
* Actors never block each other; only fences, trees, ponds, hedges, board edges,
  hay bales and temporary crates do.
* Catching a cow wins immediately, even when the resulting state was seen
  before (the game ends before the loop check).
* Repeating a full state (farmer pose + every cow pose + obstacles + items) is a
  time loop and loses.
* Running out of the step budget loses.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

from .models import (
    Actor,
    ActorTick,
    CRATE_LIFETIME,
    Cow,
    CowPersonality,
    Direction,
    GameStatus,
    Item,
    ItemKind,
    Level,
    PlacementResult,
    Pos,
    PredictionFrame,
    Rank,
    StateKey,
    TickResult,
)


def step_forward(pos: Pos, facing: Direction) -> Pos:
    """Return the tile directly in front of ``pos``."""
    dr, dc = facing.delta
    return (pos[0] + dr, pos[1] + dc)


class Board:
    """Static terrain for a level.

    The board knows nothing about actors, obstacles or items; it only answers
    whether a coordinate is inside the meadow and whether its terrain can be
    walked on.
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
        items: Iterable[Item] = (),
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
        self.items: Dict[Pos, Item] = {item.pos: item for item in level.items}
        for item in items:
            self.items[item.pos] = item
        self.stuck: Set[str] = set()
        self.steps = 0
        self.status = GameStatus.READY
        self.last_tick: Optional[TickResult] = None
        self.horn_events = 0
        self._history: List[StateKey] = [self.state_key()]

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
        return True

    def can_place_obstacle(self, pos: Pos) -> PlacementResult:
        if self.status is not GameStatus.READY:
            return PlacementResult(False, "游戏开始后不能再放置障碍")
        if not self.board.inside(pos):
            return PlacementResult(False, "不能在牧场外面放置障碍")
        if self.board.is_wall(pos):
            return PlacementResult(False, "这里已经有围栏或树木了")
        if pos in self._obstacles:
            return PlacementResult(False, "这里已经有一块干草垛了")
        if pos in self.items:
            return PlacementResult(False, "这里已经有道具了")
        if pos == self.level.farmer_start:
            return PlacementResult(False, "不能挡在农夫脚下")
        if pos in self.level.cow_positions:
            return PlacementResult(False, "不能挡在牛的脚下")
        if len(self._obstacles) >= self.level.obstacle_limit:
            return PlacementResult(False, "干草垛已经用完了")
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

    # -- items ---------------------------------------------------------
    def item_count(self, kind: ItemKind) -> int:
        return sum(1 for item in self.items.values() if item.kind is kind)

    def item_limit(self, kind: ItemKind) -> int:
        return int(self.level.item_counts.get(kind.value, 0))

    def item_left(self, kind: ItemKind) -> int:
        return max(0, self.item_limit(kind) - self.item_count(kind))

    def can_place_item(self, kind: ItemKind, pos: Pos) -> PlacementResult:
        if self.status is not GameStatus.READY:
            return PlacementResult(False, "游戏开始后不能再放置道具")
        if not self.board.inside(pos):
            return PlacementResult(False, "不能在牧场外面放置道具")
        if self.board.is_wall(pos):
            return PlacementResult(False, "这里已经有围栏或树木了")
        if pos in self._obstacles:
            return PlacementResult(False, "这里已经有干草垛了")
        if pos in self.items:
            return PlacementResult(False, "这里已经有道具了")
        if pos == self.level.farmer_start:
            return PlacementResult(False, "不能放在农夫脚下")
        if pos in self.level.cow_positions:
            return PlacementResult(False, "不能放在牛脚下")
        if self.item_left(kind) <= 0:
            return PlacementResult(False, f"{kind.label}已经用完了")
        return PlacementResult(True, "")

    def _unpaired_portal(self) -> Optional[Pos]:
        for pos, item in self.items.items():
            if item.kind is ItemKind.PORTAL and item.pair is None:
                return pos
        return None

    def place_item(self, kind: ItemKind, pos: Pos, facing: Direction = Direction.EAST) -> PlacementResult:
        result = self.can_place_item(kind, pos)
        if not result.ok:
            return result
        item = Item(
            kind=kind,
            pos=pos,
            facing=facing,
            ticks_left=CRATE_LIFETIME if kind is ItemKind.CRATE else None,
        )
        if kind is ItemKind.PORTAL:
            partner = self._unpaired_portal()
            if partner is not None:
                other = self.items[partner]
                self.items[partner] = replace(other, pair=pos)
                item = replace(item, pair=partner)
        self.items[pos] = item
        self._history = [self.state_key()]
        return PlacementResult(True, "")

    def remove_item(self, pos: Pos) -> bool:
        if self.status is not GameStatus.READY:
            return False
        item = self.items.pop(pos, None)
        if item is None:
            return False
        if item.kind is ItemKind.PORTAL and item.pair is not None:
            partner = self.items.get(item.pair)
            if partner is not None:
                self.items[item.pair] = replace(partner, pair=None)
        self._history = [self.state_key()]
        return True

    def clear_items(self) -> None:
        if self.status is not GameStatus.READY:
            return
        self.items.clear()
        self._history = [self.state_key()]

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------
    def blocked(self, pos: Pos) -> bool:
        """True when an actor cannot walk into ``pos``."""
        if not self.board.walkable(pos):
            return True
        if pos in self._obstacles:
            return True
        item = self.items.get(pos)
        if item is not None and item.kind is ItemKind.CRATE:
            return True
        return False

    def _apple_at(self, pos: Pos) -> bool:
        item = self.items.get(pos)
        return item is not None and item.kind is ItemKind.APPLE

    def state_key(self) -> StateKey:
        farmer = (self.farmer.pos[0], self.farmer.pos[1], int(self.farmer.facing))
        cows = tuple((cow.pos[0], cow.pos[1], int(cow.facing)) for cow in self.cows)
        items_key = frozenset(item.key() for item in self.items.values())
        return (farmer, cows, frozenset(self._obstacles), items_key, frozenset(self.stuck))

    @property
    def caught(self) -> bool:
        return any(cow.pos == self.farmer.pos for cow in self.cows)

    def start(self) -> None:
        if self.status is not GameStatus.READY:
            return
        # Unpaired portals are removed so the rules stay unambiguous.
        for pos in list(self.items):
            item = self.items[pos]
            if item.kind is ItemKind.PORTAL and item.pair is None:
                del self.items[pos]
        self.status = GameStatus.PLAYING
        self._history = [self.state_key()]

    # -- one tick ------------------------------------------------------
    def _advance(self, actor: Actor, key: str, personality: CowPersonality) -> ActorTick:
        if key in self.stuck:
            turned = (
                actor.facing.counter_clockwise()
                if personality is CowPersonality.STUBBORN
                else actor.facing.clockwise()
            )
            return ActorTick(actor.pos, actor.pos, actor.facing, turned, False)
        target = step_forward(actor.pos, actor.facing)
        if not self.blocked(target):
            return ActorTick(actor.pos, target, actor.facing, actor.facing, True)
        if personality is CowPersonality.GREEDY:
            for direction in (
                actor.facing.clockwise(),
                actor.facing.counter_clockwise(),
                actor.facing.opposite(),
            ):
                candidate = step_forward(actor.pos, direction)
                if self._apple_at(candidate) and not self.blocked(candidate):
                    return ActorTick(actor.pos, candidate, actor.facing, direction, True)
        turned = (
            actor.facing.counter_clockwise()
            if personality is CowPersonality.STUBBORN
            else actor.facing.clockwise()
        )
        return ActorTick(actor.pos, actor.pos, actor.facing, turned, False)

    def _apply_entry(self, actor: Actor, key: str) -> Tuple[Actor, bool]:
        """Resolve item effects for an actor that just entered its tile."""
        triggered_horn = False
        item = self.items.get(actor.pos)
        if item is not None and item.kind is ItemKind.PORTAL and item.pair is not None:
            actor = Actor(item.pair, actor.facing)
            item = self.items.get(actor.pos)
        if item is not None:
            if item.kind is ItemKind.SIGNPOST:
                actor = Actor(actor.pos, item.facing)
            elif item.kind is ItemKind.HORN:
                del self.items[actor.pos]
                triggered_horn = True
            elif item.kind is ItemKind.APPLE:
                del self.items[actor.pos]
            elif item.kind is ItemKind.MUD:
                self.stuck.add(key)
        return actor, triggered_horn

    def step(self) -> Optional[TickResult]:
        """Advance exactly one synchronous tick.

        Returns ``None`` when the game is not running any more.
        """
        if self.status is GameStatus.READY:
            self.status = GameStatus.PLAYING
        if self.status is not GameStatus.PLAYING:
            return None

        # 1. compute every next state from the current state
        farmer_tick = self._advance(self.farmer, "farmer", CowPersonality.NORMAL)
        cow_ticks = tuple(
            self._advance(cow, f"cow{index}", cow.personality)
            for index, cow in enumerate(self.cows)
        )

        # 2. commit all at once: the rule is synchronous by definition
        self.farmer = Actor(farmer_tick.end_pos, farmer_tick.end_facing)
        self.cows = tuple(
            Cow(tick.end_pos, tick.end_facing, cow.personality)
            for cow, tick in zip(self.cows, cow_ticks)
        )
        self.stuck.clear()
        self.steps += 1

        # 3. item effects, in actor order
        horn_triggered = False
        if farmer_tick.moved:
            self.farmer, horn = self._apply_entry(self.farmer, "farmer")
            horn_triggered = horn_triggered or horn
        new_cows: List[Cow] = []
        for index, (cow, tick) in enumerate(zip(self.cows, cow_ticks)):
            if tick.moved:
                resolved, horn = self._apply_entry(cow, f"cow{index}")
                horn_triggered = horn_triggered or horn
                cow = Cow(resolved.pos, resolved.facing, cow.personality)
            new_cows.append(cow)

        # 4. a blown horn reverses every cow, and timid cows retreat a step
        if horn_triggered:
            self.horn_events += 1
            reversed_cows: List[Cow] = []
            for index, cow in enumerate(new_cows):
                facing = cow.facing.opposite()
                if cow.personality is CowPersonality.TIMID:
                    retreat = step_forward(cow.pos, facing)
                    if not self.blocked(retreat):
                        moved, horn = self._apply_entry(Actor(retreat, facing), f"cow{index}")
                        reversed_cows.append(Cow(moved.pos, moved.facing, cow.personality))
                        horn_triggered = horn_triggered or horn
                        continue
                reversed_cows.append(Cow(cow.pos, facing, cow.personality))
            new_cows = reversed_cows
        self.cows = tuple(new_cows)

        # 5. temporary walls crumble
        for pos in list(self.items):
            item = self.items[pos]
            if item.ticks_left is None:
                continue
            ticked = item.ticked()
            if ticked is None:
                del self.items[pos]
            else:
                self.items[pos] = ticked

        # 6. resolution order: catch, then loop, then step budget
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
    def clone(self) -> "Simulation":
        """A playable copy used for forecasting without touching live state."""
        new = Simulation(self.level, self._obstacles, items=(), validate=False)
        new.farmer = self.farmer
        new.cows = self.cows
        new.items = dict(self.items)
        new.stuck = set(self.stuck)
        new.steps = self.steps
        new.status = GameStatus.PLAYING
        new.horn_events = self.horn_events
        new._history = list(self._history)
        return new

    def predict(self, count: int = 3) -> List[PredictionFrame]:
        """Project the next ``count`` ticks by replaying a clone."""
        if self.status.is_finished:
            return []
        frames: List[PredictionFrame] = []
        probe = self.clone()
        for index in range(1, count + 1):
            tick = probe.step()
            if tick is None:
                break
            frames.append(
                PredictionFrame(
                    step=index,
                    farmer_pos=probe.farmer.pos,
                    farmer_facing=probe.farmer.facing,
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
        return self.level.rank_for(self.steps)

    def reset(self) -> None:
        """Restart the attempt, keeping the player's layout."""
        obstacles = set(self._obstacles)
        player_items = [
            item for item in self.items.values() if item.pos not in {i.pos for i in self.level.items}
        ]
        self.__init__(self.level, obstacles, items=player_items, validate=False)

    def snapshot(self) -> Dict[str, object]:
        """Small, JSON friendly view used by the interface."""
        return {
            "steps": self.steps,
            "status": self.status.value,
            "obstacles": sorted([list(p) for p in self._obstacles]),
            "items": [
                {"kind": item.kind.value, "pos": list(item.pos)}
                for item in self.items.values()
            ],
            "farmer": [list(self.farmer.pos), int(self.farmer.facing)],
            "cows": [
                [list(cow.pos), int(cow.facing), cow.personality.value]
                for cow in self.cows
            ],
        }
