"""Data models shared by the simulation, the UI and the save layer.

The models in this module are deliberately free of any pygame dependency so that
the whole rule set can be unit tested head-less.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import FrozenSet, Iterable, Mapping, Optional, Tuple

# A board position expressed as (row, column). Row 0 is the top row.
Pos = Tuple[int, int]


class Direction(IntEnum):
    """The four cardinal directions, ordered clockwise."""

    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3

    @property
    def delta(self) -> Tuple[int, int]:
        return _DELTAS[self]

    def clockwise(self) -> "Direction":
        return Direction((self.value + 1) % 4)

    def counter_clockwise(self) -> "Direction":
        return Direction((self.value - 1) % 4)

    def opposite(self) -> "Direction":
        return Direction((self.value + 2) % 4)

    @property
    def label(self) -> str:
        return _DIRECTION_LABELS[self]


_DELTAS = {
    Direction.NORTH: (-1, 0),
    Direction.EAST: (0, 1),
    Direction.SOUTH: (1, 0),
    Direction.WEST: (0, -1),
}

_DIRECTION_LABELS = {
    Direction.NORTH: "北",
    Direction.EAST: "东",
    Direction.SOUTH: "南",
    Direction.WEST: "西",
}


class TileKind(str, Enum):
    """Visual / blocking kind of a static board tile."""

    GRASS = "grass"
    FENCE = "fence"
    TREE = "tree"
    POND = "pond"
    HEDGE = "hedge"
    FLOWERS = "flowers"

    @property
    def blocking(self) -> bool:
        return self in _BLOCKING_TILES


_BLOCKING_TILES = frozenset({TileKind.FENCE, TileKind.TREE, TileKind.POND, TileKind.HEDGE})

TILE_CHARS: Mapping[str, TileKind] = {
    ".": TileKind.GRASS,
    ",": TileKind.FLOWERS,
    "#": TileKind.FENCE,
    "T": TileKind.TREE,
    "~": TileKind.POND,
    "H": TileKind.HEDGE,
    "F": TileKind.GRASS,
    "C": TileKind.GRASS,
}

FARMER_CHAR = "F"
COW_CHAR = "C"
LEGACY_COW_CHARS = ("C", "D", "G", "S")


class TieBreak(str, Enum):
    """Chosen side when both left and right are equally good."""

    LEFT = "left"
    RIGHT = "right"


class Action(str, Enum):
    """One command for Farmer John: face an absolute direction or move."""

    TURN_TO_UP = "turn_to_up"
    TURN_TO_DOWN = "turn_to_down"
    TURN_TO_LEFT = "turn_to_left"
    TURN_TO_RIGHT = "turn_to_right"
    FORWARD = "forward"

    @property
    def label(self) -> str:
        return _ACTION_LABELS[self]

    @property
    def direction(self) -> Direction:
        """The absolute direction requested by a turn action."""
        try:
            return _ACTION_DIRECTIONS[self]
        except KeyError as exc:
            raise ValueError(f"action {self.value!r} is not a turn") from exc

    @classmethod
    def turn_to(cls, direction: Direction) -> "Action":
        return _DIRECTION_ACTIONS[direction]


_ACTION_LABELS = {
    Action.TURN_TO_UP: "朝上",
    Action.TURN_TO_DOWN: "朝下",
    Action.TURN_TO_LEFT: "朝左",
    Action.TURN_TO_RIGHT: "朝右",
    Action.FORWARD: "前进",
}

_ACTION_DIRECTIONS = {
    Action.TURN_TO_UP: Direction.NORTH,
    Action.TURN_TO_DOWN: Direction.SOUTH,
    Action.TURN_TO_LEFT: Direction.WEST,
    Action.TURN_TO_RIGHT: Direction.EAST,
}

_DIRECTION_ACTIONS = {direction: action for action, direction in _ACTION_DIRECTIONS.items()}


@dataclass(frozen=True)
class Actor:
    """A farmer or cow occupying a tile and facing a direction."""

    pos: Pos
    facing: Direction

    def turned(self, direction: Direction) -> "Actor":
        return Actor(self.pos, direction)

    def moved_to(self, pos: Pos) -> "Actor":
        return Actor(pos, self.facing)


@dataclass(frozen=True)
class Cow(Actor):
    """A cow occupying a tile and facing a direction."""


class GameStatus(str, Enum):
    PLAYING = "playing"
    WON = "won"
    LOST_EXIT = "lost_exit"
    LOST_TURNS = "lost_turns"

    @property
    def is_finished(self) -> bool:
        return self in (GameStatus.WON, GameStatus.LOST_EXIT, GameStatus.LOST_TURNS)

    @property
    def is_failure(self) -> bool:
        return self in (GameStatus.LOST_EXIT, GameStatus.LOST_TURNS)


class Rank(str, Enum):
    S = "S"
    A = "A"
    B = "B"
    C = "C"

    @property
    def label(self) -> str:
        return self.value

    @property
    def comment(self) -> str:
        return _RANK_COMMENTS[self]


_RANK_COMMENTS = {
    Rank.S: "完美预判！",
    Rank.A: "干得漂亮！",
    Rank.B: "顺利抓到了。",
    Rank.C: "有惊无险。",
}


@dataclass(frozen=True)
class Level:
    """A fully parsed, immutable level definition."""

    level_id: str
    name: str
    width: int
    height: int
    tiles: Tuple[Tuple[TileKind, ...], ...]
    farmer_start: Pos
    farmer_facing: Direction
    cow_positions: Tuple[Pos, ...]
    cow_facings: Tuple[Direction, ...]
    exit_cells: Tuple[Pos, ...] = ()
    max_turns: int = 30
    prediction_steps: int = 5
    exit_sight_range: int = -1
    sight_range: int = -1
    exit_tiebreak: TieBreak = TieBreak.RIGHT
    flee_tiebreak: TieBreak = TieBreak.RIGHT
    cows_block_sight: bool = False
    cows_block_each_other: bool = False
    obstacles: Tuple[Pos, ...] = ()
    s_threshold: int = 10
    a_threshold: int = 15
    b_threshold: int = 22
    hint: str = ""
    description: str = ""
    order: int = 0
    group: str = "main"
    source: str = "main"
    chapter: str = ""
    learning_objective: str = ""
    hint_text: Tuple[str, ...] = ()
    tags: Tuple[str, ...] = ()
    extra: Mapping[str, object] = field(default_factory=dict)

    @property
    def rows(self) -> Tuple[str, ...]:
        lookup = {v: k for k, v in TILE_CHARS.items() if k not in (FARMER_CHAR, COW_CHAR)}
        return tuple("".join(lookup[t] for t in row) for row in self.tiles)

    @property
    def cells(self) -> Iterable[Tuple[Pos, TileKind]]:
        for r, row in enumerate(self.tiles):
            for c, tile in enumerate(row):
                yield (r, c), tile

    def tile_at(self, pos: Pos) -> TileKind:
        return self.tiles[pos[0]][pos[1]]

    def is_inside(self, pos: Pos) -> bool:
        return 0 <= pos[0] < self.height and 0 <= pos[1] < self.width

    @property
    def wall_positions(self) -> FrozenSet[Pos]:
        return frozenset(p for p, t in self.cells if t.blocking)

    @property
    def blocking_positions(self) -> FrozenSet[Pos]:
        return self.wall_positions | frozenset(self.obstacles)

    def is_blocking(self, pos: Pos) -> bool:
        if not self.is_inside(pos):
            return True
        return pos in self.blocking_positions

    def is_exit(self, pos: Pos) -> bool:
        return pos in self._exit_set

    @property
    def _exit_set(self) -> FrozenSet[Pos]:
        return frozenset(self.exit_cells)

    @property
    def goal_summary(self) -> str:
        return "抓住全部牛"

    def rank_for(self, turns: int) -> Rank:
        if turns <= self.s_threshold:
            return Rank.S
        if turns <= self.a_threshold:
            return Rank.A
        if turns <= self.b_threshold:
            return Rank.B
        return Rank.C


@dataclass(frozen=True)
class ActorTick:
    start_pos: Pos
    end_pos: Pos
    start_facing: Direction
    end_facing: Direction
    moved: bool

    @property
    def turned(self) -> bool:
        return self.start_facing != self.end_facing


StateKey = Tuple[
    Tuple[int, int, int],
    Tuple[Tuple[int, int, int], ...],
    Tuple[bool, ...],
]


@dataclass(frozen=True)
class TickResult:
    farmer: ActorTick
    cows: Tuple[ActorTick, ...]
    status: GameStatus
    turns: int
    caught: Tuple[bool, ...] = ()
    caught_now: Tuple[int, ...] = ()
    escaped_index: Optional[int] = None
    loop_hint: bool = False
    blocked: bool = False
    invalid: bool = False
    message: str = ""


@dataclass(frozen=True)
class PredictionFrame:
    step: int
    cow_positions: Tuple[Pos, ...]
    cow_facings: Tuple[Direction, ...]
    caught: Tuple[bool, ...] = ()
    status: GameStatus = GameStatus.PLAYING
    escaped_index: Optional[int] = None


@dataclass(frozen=True)
class LevelResult:
    level_id: str
    cleared: bool
    best_turns: Optional[int] = None
    rank: Optional[Rank] = None
