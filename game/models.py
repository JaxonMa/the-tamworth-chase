"""Data models shared by the simulation, the UI and the save layer.

The models in this module are deliberately free of any pygame dependency so that
the whole rule set can be unit tested head-less.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Dict, FrozenSet, Iterable, Mapping, Optional, Sequence, Tuple

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


_DELTAS: Dict[Direction, Tuple[int, int]] = {
    Direction.NORTH: (-1, 0),
    Direction.EAST: (0, 1),
    Direction.SOUTH: (1, 0),
    Direction.WEST: (0, -1),
}

_DIRECTION_LABELS: Dict[Direction, str] = {
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
COW_CHARS = ("C", "D", "G", "S")  # C=normal, D=stubborn, G=greedy, S=timid


class CowPersonality(str, Enum):
    """Behaviour profile of a cow."""

    NORMAL = "normal"
    STUBBORN = "stubborn"   # turns counter clockwise when blocked
    GREEDY = "greedy"       # prefers a neighbouring apple when blocked
    TIMID = "timid"         # retreats one tile when a horn is blown nearby

    @property
    def label(self) -> str:
        return _PERSONALITY_LABELS[self]

    @property
    def description(self) -> str:
        return _PERSONALITY_TEXT[self]


_PERSONALITY_LABELS = {
    CowPersonality.NORMAL: "普通牛",
    CowPersonality.STUBBORN: "倔牛",
    CowPersonality.GREEDY: "贪吃牛",
    CowPersonality.TIMID: "胆小牛",
}

_PERSONALITY_TEXT = {
    CowPersonality.NORMAL: "被挡住时顺时针转身。",
    CowPersonality.STUBBORN: "被挡住时逆时针转身。",
    CowPersonality.GREEDY: "附近有苹果时会先走过去吃。",
    CowPersonality.TIMID: "听到喇叭声会后退一步。",
}

PERSONALITY_BY_CHAR: Mapping[str, CowPersonality] = {
    "C": CowPersonality.NORMAL,
    "D": CowPersonality.STUBBORN,
    "G": CowPersonality.GREEDY,
    "S": CowPersonality.TIMID,
}


class ItemKind(str, Enum):
    """Placeable tools that modify the chase."""

    APPLE = "apple"
    MUD = "mud"
    CRATE = "crate"
    SIGNPOST = "signpost"
    HORN = "horn"
    PORTAL = "portal"

    @property
    def label(self) -> str:
        return _ITEM_LABELS[self]

    @property
    def short_label(self) -> str:
        return _ITEM_SHORT_LABELS[self]

    @property
    def description(self) -> str:
        return _ITEM_TEXT[self]


_ITEM_LABELS = {
    ItemKind.APPLE: "苹果",
    ItemKind.MUD: "泥地",
    ItemKind.CRATE: "临时木墙",
    ItemKind.SIGNPOST: "路标",
    ItemKind.HORN: "喇叭",
    ItemKind.PORTAL: "成对传送门",
}

_ITEM_SHORT_LABELS = {
    ItemKind.APPLE: "苹果",
    ItemKind.MUD: "泥地",
    ItemKind.CRATE: "木墙",
    ItemKind.SIGNPOST: "路标",
    ItemKind.HORN: "喇叭",
    ItemKind.PORTAL: "传送门",
}

_ITEM_TEXT = {
    ItemKind.APPLE: "贪吃牛会优先走向苹果，任何角色经过都会吃掉它。",
    ItemKind.MUD: "踩进泥地的角色下一回合会陷住，只能原地转身。",
    ItemKind.CRATE: "临时木墙会阻挡 8 个回合，然后自己散开。",
    ItemKind.SIGNPOST: "角色踩上路标后会立刻转向箭头方向。",
    ItemKind.HORN: "踩到喇叭时所有牛掉头，胆小牛还会后退一步。",
    ItemKind.PORTAL: "成对出现，角色踩进去会从另一扇门出来。",
}

PORTAL_LIFETIME = 8
CRATE_LIFETIME = 8


@dataclass(frozen=True)
class Item:
    """An item on the board.  Instances are replaced, never mutated in place."""

    kind: ItemKind
    pos: Pos
    facing: Direction = Direction.EAST
    ticks_left: Optional[int] = None
    pair: Optional[Pos] = None

    def ticked(self) -> Optional["Item"]:
        if self.ticks_left is None:
            return self
        remaining = self.ticks_left - 1
        if remaining <= 0:
            return None
        return Item(self.kind, self.pos, self.facing, remaining, self.pair)

    def key(self) -> Tuple[str, int, int, int, int]:
        return (
            self.kind.value,
            self.pos[0],
            self.pos[1],
            int(self.facing),
            -1 if self.ticks_left is None else int(self.ticks_left),
        )


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
    """A cow with a behaviour personality."""

    personality: CowPersonality = CowPersonality.NORMAL


class GameStatus(str, Enum):
    READY = "ready"
    PLAYING = "playing"
    WON = "won"
    LOST_STEPS = "lost_steps"
    LOST_LOOP = "lost_loop"

    @property
    def is_finished(self) -> bool:
        return self in (GameStatus.WON, GameStatus.LOST_STEPS, GameStatus.LOST_LOOP)

    @property
    def is_failure(self) -> bool:
        return self in (GameStatus.LOST_STEPS, GameStatus.LOST_LOOP)


class Rank(str, Enum):
    """Step based performance grade."""

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
    cow_personalities: Tuple[CowPersonality, ...] = ()
    obstacle_limit: int = 3
    step_limit: int = 60
    s_threshold: int = 12
    a_threshold: int = 20
    b_threshold: int = 30
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
    apple_positions: Tuple[Pos, ...] = ()
    items: Tuple[Item, ...] = ()
    item_counts: Mapping[str, int] = field(default_factory=dict)
    extra: Mapping[str, object] = field(default_factory=dict)

    @property
    def rows(self) -> Tuple[str, ...]:
        """Re-serialise the tiles to grid characters (used by the editor)."""
        lookup = {v: k for k, v in TILE_CHARS.items() if k not in (FARMER_CHAR, "C")}
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

    def rank_for(self, steps: int) -> Rank:
        if steps <= self.s_threshold:
            return Rank.S
        if steps <= self.a_threshold:
            return Rank.A
        if steps <= self.b_threshold:
            return Rank.B
        return Rank.C

    @property
    def has_tutorial(self) -> bool:
        return bool(self.tips) or self.source == "tutorial"


@dataclass(frozen=True)
class ActorTick:
    """Snapshot of one actor before and after a single simulation tick."""

    start_pos: Pos
    end_pos: Pos
    start_facing: Direction
    end_facing: Direction
    moved: bool

    @property
    def turned(self) -> bool:
        return self.start_facing != self.end_facing


StateKey = Tuple[Tuple[int, int, int], Tuple[Tuple[int, int, int], ...], FrozenSet[Pos]]


@dataclass(frozen=True)
class TickResult:
    """Everything the renderer needs to animate one synchronous tick."""

    farmer: ActorTick
    cows: Tuple[ActorTick, ...]
    status: GameStatus
    steps: int
    caught: bool = False
    loop_hit: bool = False


@dataclass(frozen=True)
class PredictionFrame:
    """One projected future state used by the three-step preview."""

    step: int
    farmer_pos: Pos
    farmer_facing: Direction
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
    best_steps: Optional[int] = None
    rank: Optional[Rank] = None
    obstacles_used: int = 0
