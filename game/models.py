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
        """Return the (row, column) offset for one step in this direction."""
        return _DELTAS[self]

    def clockwise(self) -> "Direction":
        return Direction((self.value + 1) % 4)

    def counter_clockwise(self) -> "Direction":
        return Direction((self.value - 1) % 4)

    def opposite(self) -> "Direction":
        return Direction((self.value + 2) % 4)

    @property
    def label(self) -> str:
        """Chinese label used in the interface."""
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

# Characters accepted inside a level grid.
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
# Legacy maps read "D", "G" and "S" as ordinary cows; personalities are gone.
LEGACY_COW_CHARS = ("C", "D", "G", "S")


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
    """A cow.  Cows share the farmer's movement rules but never react to him."""


class GameStatus(str, Enum):
    READY = "ready"
    PLAYING = "playing"
    WON = "won"
    LOST_TURNS = "lost_turns"

    @property
    def is_finished(self) -> bool:
        return self in (GameStatus.WON, GameStatus.LOST_TURNS)

    @property
    def is_failure(self) -> bool:
        return self is GameStatus.LOST_TURNS


class WinCondition(str, Enum):
    """How a level is won."""

    CATCH = "catch"
    PEN = "pen"


class Rank(str, Enum):
    """Turn based performance grade."""

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
    Rank.B: "顺利抓到啦。",
    Rank.C: "有惊无险。",
}


@dataclass(frozen=True)
class Tip:
    """One tutorial hint bound to a gameplay trigger."""

    trigger: str
    text: str


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
    max_turns: int = 30
    initial_obstacles: int = 3
    prediction_steps: int = 5
    win_condition: WinCondition = WinCondition.CATCH
    pen_cells: Tuple[Pos, ...] = ()
    cows_block_each_other: bool = False
    s_threshold: int = 10
    a_threshold: int = 15
    b_threshold: int = 22
    hint: str = ""
    description: str = ""
    order: int = 0
    group: str = "main"
    source: str = "main"
    tags: Tuple[str, ...] = ()
    tutorial_id: str = ""
    goal_text: str = ""
    tips: Tuple[Tip, ...] = ()
    practice_text: str = ""
    extra: Mapping[str, object] = field(default_factory=dict)

    @property
    def rows(self) -> Tuple[str, ...]:
        """Re-serialise the tiles to grid characters (used by the editor)."""
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

    def is_blocking(self, pos: Pos) -> bool:
        return not self.is_inside(pos) or self.tile_at(pos).blocking

    @property
    def wall_positions(self) -> FrozenSet[Pos]:
        return frozenset(p for p, t in self.cells if t.blocking)

    def rank_for(self, turns: int) -> Rank:
        if turns <= self.s_threshold:
            return Rank.S
        if turns <= self.a_threshold:
            return Rank.A
        if turns <= self.b_threshold:
            return Rank.B
        return Rank.C

    @property
    def has_tutorial(self) -> bool:
        return bool(self.tips) or self.source == "tutorial"

    @property
    def is_pen_level(self) -> bool:
        return self.win_condition is WinCondition.PEN

    @property
    def goal_summary(self) -> str:
        """Short, player facing description of the win condition."""
        if self.is_pen_level:
            return f"把 {len(self.cow_positions)} 头牛赶进围栏格"
        if len(self.cow_positions) > 1:
            return f"抓住任意一头牛（共 {len(self.cow_positions)} 头）"
        return "抓住牛"


@dataclass(frozen=True)
class ActorTick:
    """Snapshot of one actor before and after a single turn."""

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
    FrozenSet[Pos],
    int,
    str,
]


@dataclass(frozen=True)
class TickResult:
    """Everything the renderer needs to animate one turn."""

    farmer: ActorTick
    cows: Tuple[ActorTick, ...]
    status: GameStatus
    turns: int
    caught: bool = False
    penned: bool = False
    loop_hint: bool = False
    blocked: bool = False
    message: str = ""


@dataclass(frozen=True)
class PredictionFrame:
    """One projected future state used by the configurable path preview."""

    step: int
    cow_positions: Tuple[Pos, ...]
    cow_facings: Tuple[Direction, ...]
    status: GameStatus


@dataclass(frozen=True)
class PlacementResult:
    ok: bool
    message: str = ""


@dataclass(frozen=True)
class LevelResult:
    """Outcome of a finished level, stored in the save file."""

    level_id: str
    cleared: bool
    best_turns: Optional[int] = None
    rank: Optional[Rank] = None
    obstacles_used: int = 0
