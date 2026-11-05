"""Level editor model: terrain painting, actor placement and JSON exchange.

The editor works on a mutable grid and converts it into a regular :class:`Level`
so the very same simulation runs in test-play.  Export/import is plain JSON in
``custom_levels/`` next to the game.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .levels import LevelError, level_to_dict, parse_level
from .models import (
    COW_CHARS,
    FARMER_CHAR,
    CowPersonality,
    Direction,
    Item,
    ItemKind,
    Level,
    PERSONALITY_BY_CHAR,
    Pos,
    TileKind,
)
from .paths import custom_levels_dir

PAINT_TILES: Tuple[TileKind, ...] = (
    TileKind.GRASS,
    TileKind.FENCE,
    TileKind.HEDGE,
    TileKind.TREE,
    TileKind.POND,
)

_TILE_TO_CHAR = {
    TileKind.GRASS: ".",
    TileKind.FENCE: "#",
    TileKind.HEDGE: "H",
    TileKind.TREE: "T",
    TileKind.POND: "~",
    TileKind.FLOWERS: ",",
}

_COW_CHAR = {
    CowPersonality.NORMAL: "C",
    CowPersonality.STUBBORN: "D",
    CowPersonality.GREEDY: "G",
    CowPersonality.TIMID: "S",
}


@dataclass
class EditorModel:
    """Mutable editing state for one level."""

    width: int = 10
    height: int = 10
    tiles: List[List[TileKind]] = field(default_factory=list)
    farmer: Pos = (8, 1)
    farmer_facing: Direction = Direction.EAST
    cows: List[Tuple[Pos, Direction, CowPersonality]] = field(default_factory=list)
    obstacle_limit: int = 3
    step_limit: int = 40
    name: str = "我的牧场"

    def __post_init__(self) -> None:
        if not self.tiles:
            self.reset()
        if not self.cows:
            self.cows = [((1, 8), Direction.NORTH, CowPersonality.NORMAL)]

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """A fenced meadow with the farmer bottom-left and a cow top-right."""
        self.tiles = []
        for row in range(self.height):
            line: List[TileKind] = []
            for col in range(self.width):
                border = row in (0, self.height - 1) or col in (0, self.width - 1)
                line.append(TileKind.FENCE if border else TileKind.GRASS)
            self.tiles.append(line)
        self.farmer = (self.height - 2, 1)
        self.farmer_facing = Direction.EAST
        self.cows = [((1, self.width - 2), Direction.NORTH, CowPersonality.NORMAL)]

    @classmethod
    def from_level(cls, level: Level) -> "EditorModel":
        rows = level_to_dict(level)["grid"]
        model = cls(width=level.width, height=level.height)
        model.tiles = []
        for row, text in enumerate(rows):
            line: List[TileKind] = []
            for col, char in enumerate(text):
                pos = (row, col)
                if pos == level.farmer_start:
                    line.append(TileKind.GRASS)
                elif char in COW_CHARS:
                    line.append(TileKind.GRASS)
                else:
                    line.append(_char_to_tile(char))
            model.tiles.append(line)
        model.farmer = level.farmer_start
        model.farmer_facing = level.farmer_facing
        model.cows = [
            (pos, facing, personality)
            for pos, facing, personality in zip(
                level.cow_positions, level.cow_facings, level.cow_personalities
            )
        ]
        model.obstacle_limit = level.obstacle_limit
        model.step_limit = level.step_limit
        model.name = level.name
        return model

    # ------------------------------------------------------------------
    def inside(self, pos: Pos) -> bool:
        return 0 <= pos[0] < self.height and 0 <= pos[1] < self.width

    def set_tile(self, pos: Pos, kind: TileKind) -> bool:
        if not self.inside(pos):
            return False
        if pos == self.farmer or any(cow[0] == pos for cow in self.cows):
            return False
        self.tiles[pos[0]][pos[1]] = kind
        return True

    def cycle_tile(self, pos: Pos) -> None:
        if not self.inside(pos):
            return
        current = self.tiles[pos[0]][pos[1]]
        try:
            index = PAINT_TILES.index(current)
        except ValueError:
            index = 0
        self.set_tile(pos, PAINT_TILES[(index + 1) % len(PAINT_TILES)])

    def move_farmer(self, pos: Pos) -> bool:
        if not self.inside(pos):
            return False
        if any(cow[0] == pos for cow in self.cows):
            return False
        self.tiles[pos[0]][pos[1]] = TileKind.GRASS
        self.farmer = pos
        return True

    def cycle_cow_personality(self) -> None:
        if not self.cows:
            self.add_cow(self.find_free_cell())
            return
        pos, facing, personality = self.cows[0]
        order = list(CowPersonality)
        index = (order.index(personality) + 1) % len(order)
        self.cows[0] = (pos, facing, order[index])

    def move_cow(self, pos: Pos) -> bool:
        if not self.inside(pos) or pos == self.farmer:
            return False
        self.tiles[pos[0]][pos[1]] = TileKind.GRASS
        if self.cows:
            _, facing, personality = self.cows[0]
            self.cows[0] = (pos, facing, personality)
        else:
            self.cows = [(pos, Direction.NORTH, CowPersonality.NORMAL)]
        return True

    def add_cow(self, pos: Pos) -> bool:
        if not self.inside(pos) or pos == self.farmer:
            return False
        if len(self.cows) >= 2:
            return False
        if any(cow[0] == pos for cow in self.cows):
            return False
        self.cows.append((pos, Direction.NORTH, CowPersonality.NORMAL))
        return True

    def find_free_cell(self) -> Pos:
        for row in range(1, self.height - 1):
            for col in range(1, self.width - 1):
                if (
                    (row, col) != self.farmer
                    and not any(cow[0] == (row, col) for cow in self.cows)
                    and self.tiles[row][col] is TileKind.GRASS
                ):
                    return (row, col)
        return (self.height // 2, self.width // 2)

    def cycle_facing(self) -> None:
        self.farmer_facing = self.farmer_facing.clockwise()

    def cycle_cow_facing(self) -> None:
        if not self.cows:
            return
        pos, facing, personality = self.cows[0]
        self.cows[0] = (pos, facing.clockwise(), personality)

    # ------------------------------------------------------------------
    def to_grid(self) -> List[str]:
        rows: List[str] = []
        for row in range(self.height):
            chars: List[str] = []
            for col in range(self.width):
                pos = (row, col)
                if pos == self.farmer:
                    chars.append(FARMER_CHAR)
                else:
                    cow = next((cow for cow in self.cows if cow[0] == pos), None)
                    if cow is not None:
                        chars.append(_COW_CHAR[cow[2]])
                    else:
                        chars.append(_TILE_TO_CHAR.get(self.tiles[row][col], "."))
            rows.append("".join(chars))
        return rows

    def to_payload(self, level_id: Optional[str] = None) -> Dict[str, object]:
        return {
            "id": level_id or "custom_level",
            "name": self.name,
            "description": "来自本地编辑器的牧场",
            "hint": "自己设计的牧场，慢慢来。",
            "grid": self.to_grid(),
            "farmer_facing": self.farmer_facing.name.lower(),
            "cow_facings": [cow[1].name.lower() for cow in self.cows],
            "cow_personalities": [cow[2].value for cow in self.cows],
            "obstacle_limit": self.obstacle_limit,
            "step_limit": self.step_limit,
            "s_threshold": max(1, self.step_limit // 3),
            "a_threshold": max(2, self.step_limit // 2),
            "b_threshold": max(3, self.step_limit * 3 // 4),
        }

    def to_level(self, level_id: str = "custom_level") -> Level:
        return parse_level(self.to_payload(level_id), source="custom", group="custom")

    def validate(self) -> List[str]:
        problems: List[str] = []
        if not any(True for _ in self.cows):
            problems.append("至少需要一头牛")
        if self.farmer == (0, 0):
            problems.append("还没有放农夫")
        if self.obstacle_limit < 0:
            problems.append("障碍上限不能为负")
        if self.step_limit < 5:
            problems.append("步数上限至少为 5")
        # the actors must stand on walkable tiles
        if not self.inside(self.farmer):
            problems.append("农夫不在牧场里")
        for pos, _facing, _personality in self.cows:
            if not self.inside(pos):
                problems.append("牛不在牧场里")
        return problems


def _char_to_tile(char: str) -> TileKind:
    for kind, value in _TILE_TO_CHAR.items():
        if value == char:
            return kind
    return TileKind.GRASS


# ---------------------------------------------------------------------------
# Export / import
# ---------------------------------------------------------------------------
def _slugify(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", name).strip("_")
    return cleaned or "custom_level"


def export_level(level: Level, directory: Optional[Path] = None) -> Path:
    """Write a level to ``custom_levels/`` and return the file path."""
    target_dir = Path(directory) if directory else custom_levels_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    level_id = f"custom_{stamp}"
    payload = level_to_dict(level)
    payload["id"] = level_id
    payload["exported_at"] = stamp
    bundle = {"version": 1, "levels": [payload]}
    path = target_dir / f"{_slugify(level.name)}_{stamp}.json"
    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def list_custom_levels(directory: Optional[Path] = None) -> List[Path]:
    target = Path(directory) if directory else custom_levels_dir()
    if not target.exists():
        return []
    return sorted(target.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def import_level(path: Path) -> Level:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = raw.get("levels") if isinstance(raw, dict) else None
    if not isinstance(items, list) or not items:
        raise LevelError(f"{Path(path).name} 里没有关卡数据")
    return parse_level(items[0], source="custom", group="custom")
