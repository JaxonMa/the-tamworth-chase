"""Level editor model: terrain, exits, actors and JSON exchange."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Set, Tuple

from .levels import LevelError, level_to_dict, parse_level
from .models import (
    COW_CHAR,
    FARMER_CHAR,
    Direction,
    Level,
    Pos,
    TileKind,
    TieBreak,
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

MAX_COWS = 3


@dataclass
class EditorModel:
    """Mutable editing state for one level."""

    width: int = 10
    height: int = 10
    tiles: List[List[TileKind]] = field(default_factory=list)
    farmer: Pos = (5, 5)
    farmer_facing: Direction = Direction.NORTH
    cows: List[Tuple[Pos, Direction]] = field(default_factory=list)
    active_cow: int = 0
    exits: Set[Pos] = field(default_factory=set)
    obstacles: Set[Pos] = field(default_factory=set)
    max_turns: int = 30
    prediction_steps: int = 5
    sight_range: int = -1
    exit_sight_range: int = -1
    exit_tiebreak: TieBreak = TieBreak.RIGHT
    flee_tiebreak: TieBreak = TieBreak.RIGHT
    cows_block_sight: bool = False
    cows_block_each_other: bool = False
    name: str = "我的牧场"

    def __post_init__(self) -> None:
        if not self.tiles:
            self.reset()
        if not self.cows:
            self.cows = [((1, 8), Direction.NORTH)]
        if not self.exits:
            self.exits = {(1, 1)}

    # ------------------------------------------------------------------
    def reset(self) -> None:
        self.tiles = []
        for row in range(self.height):
            line: List[TileKind] = []
            for col in range(self.width):
                border = row in (0, self.height - 1) or col in (0, self.width - 1)
                line.append(TileKind.FENCE if border else TileKind.GRASS)
            self.tiles.append(line)
        self.farmer = (5, 5)
        self.farmer_facing = Direction.NORTH
        self.cows = [((1, self.width - 2), Direction.NORTH)]
        self.active_cow = 0
        self.exits = {(1, 1)}
        self.obstacles = set()
        self.max_turns = 30
        self.prediction_steps = 5
        self.sight_range = -1
        self.exit_sight_range = -1
        self.exit_tiebreak = TieBreak.RIGHT
        self.flee_tiebreak = TieBreak.RIGHT
        self.cows_block_sight = False
        self.cows_block_each_other = False

    @classmethod
    def from_level(cls, level: Level) -> "EditorModel":
        model = cls(width=level.width, height=level.height)
        model.tiles = [list(row) for row in level.tiles]
        for pos in (level.farmer_start, *level.cow_positions):
            model.tiles[pos[0]][pos[1]] = TileKind.GRASS
        model.farmer = level.farmer_start
        model.farmer_facing = level.farmer_facing
        model.cows = [
            (pos, facing)
            for pos, facing in zip(level.cow_positions, level.cow_facings)
        ]
        model.active_cow = 0
        model.exits = set(level.exit_cells)
        model.obstacles = set(level.obstacles)
        model.max_turns = level.max_turns
        model.prediction_steps = level.prediction_steps
        model.sight_range = level.sight_range
        model.exit_sight_range = level.exit_sight_range
        model.exit_tiebreak = level.exit_tiebreak
        model.flee_tiebreak = level.flee_tiebreak
        model.cows_block_sight = level.cows_block_sight
        model.cows_block_each_other = level.cows_block_each_other
        model.name = level.name
        return model

    # ------------------------------------------------------------------
    def inside(self, pos: Pos) -> bool:
        return 0 <= pos[0] < self.height and 0 <= pos[1] < self.width

    def is_wall(self, pos: Pos) -> bool:
        return self.inside(pos) and self.tiles[pos[0]][pos[1]].blocking

    def actor_at(self, pos: Pos) -> bool:
        return pos == self.farmer or any(cow[0] == pos for cow in self.cows)

    def blocked(self, pos: Pos) -> bool:
        return self.is_wall(pos) or pos in self.obstacles

    def set_tile(self, pos: Pos, kind: TileKind) -> bool:
        if not self.inside(pos) or self.actor_at(pos):
            return False
        self.tiles[pos[0]][pos[1]] = kind
        if kind.blocking:
            self.exits.discard(pos)
            self.obstacles.discard(pos)
        return True

    def toggle_exit(self, pos: Pos) -> bool:
        if not self.inside(pos) or self.blocked(pos) or self.actor_at(pos):
            return False
        if pos in self.exits:
            self.exits.discard(pos)
        else:
            self.exits.add(pos)
        return True

    def toggle_obstacle(self, pos: Pos) -> bool:
        if not self.inside(pos) or self.is_wall(pos) or self.actor_at(pos):
            return False
        if pos in self.obstacles:
            self.obstacles.discard(pos)
        else:
            if pos in self.exits:
                self.exits.discard(pos)
            self.obstacles.add(pos)
        return True

    def move_farmer(self, pos: Pos) -> bool:
        if not self.inside(pos) or self.blocked(pos):
            return False
        if any(cow[0] == pos for cow in self.cows):
            return False
        self.tiles[pos[0]][pos[1]] = TileKind.GRASS
        self.exits.discard(pos)
        self.farmer = pos
        return True

    def move_cow(self, pos: Pos) -> bool:
        if not self.inside(pos) or self.blocked(pos) or pos == self.farmer:
            return False
        if any(cow[0] == pos for cow in self.cows):
            return False
        self.tiles[pos[0]][pos[1]] = TileKind.GRASS
        self.exits.discard(pos)
        if not self.cows:
            self.cows = [(pos, Direction.NORTH)]
            self.active_cow = 0
        else:
            self.active_cow = min(self.active_cow, len(self.cows) - 1)
            _, facing = self.cows[self.active_cow]
            self.cows[self.active_cow] = (pos, facing)
        return True

    def add_cow(self, pos: Optional[Pos] = None) -> bool:
        if len(self.cows) >= MAX_COWS:
            return False
        target = pos if pos is not None else self.find_free_cell()
        if target is None or not self.inside(target) or self.blocked(target):
            return False
        if target == self.farmer or any(cow[0] == target for cow in self.cows):
            return False
        self.tiles[target[0]][target[1]] = TileKind.GRASS
        self.exits.discard(target)
        self.cows.append((target, Direction.NORTH))
        self.active_cow = len(self.cows) - 1
        return True

    def remove_cow(self) -> bool:
        if len(self.cows) <= 1:
            return False
        self.cows.pop()
        self.active_cow = min(self.active_cow, len(self.cows) - 1)
        return True

    def find_free_cell(self) -> Pos:
        for row in range(1, self.height - 1):
            for col in range(1, self.width - 1):
                pos = (row, col)
                if (
                    pos != self.farmer
                    and not any(cow[0] == pos for cow in self.cows)
                    and self.tiles[row][col] is TileKind.GRASS
                    and pos not in self.exits
                    and pos not in self.obstacles
                ):
                    return pos
        return (self.height // 2, self.width // 2)

    def cycle_facing(self) -> None:
        self.farmer_facing = self.farmer_facing.clockwise()

    def cycle_cow_facing(self) -> None:
        if not self.cows:
            return
        self.active_cow = min(self.active_cow, len(self.cows) - 1)
        pos, facing = self.cows[self.active_cow]
        self.cows[self.active_cow] = (pos, facing.clockwise())

    def cycle_active_cow(self) -> None:
        if len(self.cows) > 1:
            self.active_cow = (self.active_cow + 1) % len(self.cows)

    def cycle_exit_tiebreak(self) -> None:
        self.exit_tiebreak = (
            TieBreak.LEFT if self.exit_tiebreak is TieBreak.RIGHT else TieBreak.RIGHT
        )

    def cycle_flee_tiebreak(self) -> None:
        self.flee_tiebreak = (
            TieBreak.LEFT if self.flee_tiebreak is TieBreak.RIGHT else TieBreak.RIGHT
        )

    def toggle_block_sight(self) -> None:
        self.cows_block_sight = not self.cows_block_sight

    def toggle_block_each_other(self) -> None:
        self.cows_block_each_other = not self.cows_block_each_other

    # ------------------------------------------------------------------
    def to_grid(self) -> List[str]:
        rows: List[str] = []
        for row in range(self.height):
            chars: List[str] = []
            for col in range(self.width):
                pos = (row, col)
                if pos == self.farmer:
                    chars.append(FARMER_CHAR)
                elif any(cow[0] == pos for cow in self.cows):
                    chars.append(COW_CHAR)
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
            "fj_start_direction": self.farmer_facing.name.lower(),
            "cow_facings": [cow[1].name.lower() for cow in self.cows],
            "exit_cells": [list(pos) for pos in sorted(self.exits)],
            "obstacles": [list(pos) for pos in sorted(self.obstacles)],
            "max_turns": self.max_turns,
            "prediction_steps": self.prediction_steps,
            "sight_range": self.sight_range,
            "exit_sight_range": self.exit_sight_range,
            "exit_tiebreak": self.exit_tiebreak.value,
            "flee_tiebreak": self.flee_tiebreak.value,
            "cows_block_sight": self.cows_block_sight,
            "cows_block_each_other": self.cows_block_each_other,
            "s_threshold": max(1, self.max_turns // 3),
            "a_threshold": max(2, self.max_turns // 2),
            "b_threshold": max(3, self.max_turns * 3 // 4),
        }

    def to_level(self, level_id: str = "custom_level") -> Level:
        return parse_level(self.to_payload(level_id), source="custom", group="custom")

    def validate(self) -> List[str]:
        problems: List[str] = []
        if not self.cows:
            problems.append("至少需要一头牛")
        if not self.inside(self.farmer):
            problems.append("农夫不在牧场里")
        if not self.exits:
            problems.append("至少需要一格出口")
        if self.max_turns < 5:
            problems.append("回合上限至少为 5")
        if self.prediction_steps < 0 or self.prediction_steps > 20:
            problems.append("预测步数必须在 0 到 20 之间")
        for pos in self.exits:
            if not self.inside(pos) or self.blocked(pos) or self.actor_at(pos):
                problems.append("出口不能落在障碍或角色脚下")
                break
        for pos in self.obstacles:
            if not self.inside(pos) or self.is_wall(pos) or self.actor_at(pos):
                problems.append("固定障碍不能落在墙或角色脚下")
                break
        positions = [cow[0] for cow in self.cows]
        if len(set(positions)) != len(positions):
            problems.append("两头牛不能站在同一格")
        if self.farmer in positions:
            problems.append("农夫和牛不能站在同一格")
        return problems


# ---------------------------------------------------------------------------
# Export / import
# ---------------------------------------------------------------------------
def _slugify(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", name).strip("_")
    return cleaned or "custom_level"


def export_level(
    level: Level,
    directory: Optional[Path] = None,
    *,
    verification: Optional[Mapping[str, object]] = None,
) -> Path:
    target_dir = Path(directory) if directory else custom_levels_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    level_id = f"custom_{stamp}"
    payload = level_to_dict(level)
    payload["id"] = level_id
    payload["exported_at"] = stamp
    if verification is not None:
        payload["verification"] = dict(verification)
    bundle = {"version": 5, "game": "The Tamworth Chase", "levels": [payload]}
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
