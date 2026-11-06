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
from typing import Dict, List, Optional, Set, Tuple

from .levels import LevelError, level_to_dict, parse_level
from .models import (
    COW_CHAR,
    FARMER_CHAR,
    Direction,
    Level,
    Pos,
    TileKind,
    WinCondition,
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
    farmer: Pos = (8, 1)
    farmer_facing: Direction = Direction.EAST
    cows: List[Tuple[Pos, Direction]] = field(default_factory=list)
    max_turns: int = 30
    initial_obstacles: int = 3
    prediction_steps: int = 5
    win_condition: WinCondition = WinCondition.CATCH
    pen_cells: Set[Pos] = field(default_factory=set)
    cows_block_each_other: bool = False
    name: str = "我的牧场"

    def __post_init__(self) -> None:
        if not self.tiles:
            self.reset()
        if not self.cows:
            self.cows = [((1, 8), Direction.NORTH)]

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
        self.cows = [((1, self.width - 2), Direction.NORTH)]
        self.pen_cells = set()
        self.win_condition = WinCondition.CATCH
        self.max_turns = 30
        self.initial_obstacles = 3
        self.prediction_steps = 5
        self.cows_block_each_other = False

    @classmethod
    def from_level(cls, level: Level) -> "EditorModel":
        rows = level_to_dict(level)["grid"]
        model = cls(width=level.width, height=level.height)
        model.tiles = []
        for row, text in enumerate(rows):
            line: List[TileKind] = []
            for col, char in enumerate(text):
                pos = (row, col)
                if pos == level.farmer_start or char == COW_CHAR:
                    line.append(TileKind.GRASS)
                else:
                    line.append(_char_to_tile(char))
            model.tiles.append(line)
        model.farmer = level.farmer_start
        model.farmer_facing = level.farmer_facing
        model.cows = list(zip(level.cow_positions, level.cow_facings))
        model.max_turns = level.max_turns
        model.initial_obstacles = level.initial_obstacles
        model.prediction_steps = level.prediction_steps
        model.win_condition = level.win_condition
        model.pen_cells = set(level.pen_cells)
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

    def set_tile(self, pos: Pos, kind: TileKind) -> bool:
        if not self.inside(pos):
            return False
        if self.actor_at(pos):
            return False
        self.tiles[pos[0]][pos[1]] = kind
        if kind.blocking:
            self.pen_cells.discard(pos)
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

    def toggle_pen(self, pos: Pos) -> bool:
        if not self.inside(pos) or self.is_wall(pos) or self.actor_at(pos):
            return False
        if pos in self.pen_cells:
            self.pen_cells.discard(pos)
        else:
            self.pen_cells.add(pos)
        return True

    def move_farmer(self, pos: Pos) -> bool:
        if not self.inside(pos) or self.is_wall(pos):
            return False
        if any(cow[0] == pos for cow in self.cows):
            return False
        self.tiles[pos[0]][pos[1]] = TileKind.GRASS
        self.pen_cells.discard(pos)
        self.farmer = pos
        return True

    def move_cow(self, pos: Pos) -> bool:
        if not self.inside(pos) or pos == self.farmer or self.is_wall(pos):
            return False
        if any(cow[0] == pos for cow in self.cows):
            return False
        self.tiles[pos[0]][pos[1]] = TileKind.GRASS
        self.pen_cells.discard(pos)
        if self.cows:
            _, facing = self.cows[0]
            self.cows[0] = (pos, facing)
        else:
            self.cows = [(pos, Direction.NORTH)]
        return True

    def add_cow(self, pos: Optional[Pos] = None) -> bool:
        if len(self.cows) >= MAX_COWS:
            return False
        target = pos if pos is not None else self.find_free_cell()
        if target is None or not self.inside(target) or target == self.farmer:
            return False
        if self.is_wall(target) or any(cow[0] == target for cow in self.cows):
            return False
        self.tiles[target[0]][target[1]] = TileKind.GRASS
        self.pen_cells.discard(target)
        self.cows.append((target, Direction.NORTH))
        return True

    def remove_cow(self) -> bool:
        if len(self.cows) <= 1:
            return False
        self.cows.pop()
        return True

    def find_free_cell(self) -> Pos:
        for row in range(1, self.height - 1):
            for col in range(1, self.width - 1):
                pos = (row, col)
                if (
                    pos != self.farmer
                    and not any(cow[0] == pos for cow in self.cows)
                    and self.tiles[row][col] is TileKind.GRASS
                ):
                    return pos
        return (self.height // 2, self.width // 2)

    def cycle_facing(self) -> None:
        self.farmer_facing = self.farmer_facing.clockwise()

    def cycle_cow_facing(self) -> None:
        if not self.cows:
            return
        pos, facing = self.cows[0]
        self.cows[0] = (pos, facing.clockwise())

    def cycle_win_condition(self) -> None:
        self.win_condition = (
            WinCondition.PEN
            if self.win_condition is WinCondition.CATCH
            else WinCondition.CATCH
        )

    def toggle_cow_blocking(self) -> None:
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
            "farmer_facing": self.farmer_facing.name.lower(),
            "cow_facings": [cow[1].name.lower() for cow in self.cows],
            "max_turns": self.max_turns,
            "initial_obstacles": self.initial_obstacles,
            "prediction_steps": self.prediction_steps,
            "win_condition": self.win_condition.value,
            "pen_cells": [list(pos) for pos in sorted(self.pen_cells)],
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
        if self.max_turns < 5:
            problems.append("回合上限至少为 5")
        if self.initial_obstacles < 0:
            problems.append("障碍数量不能为负")
        if self.prediction_steps < 0 or self.prediction_steps > 20:
            problems.append("预测步数必须在 0 到 20 之间")
        if self.win_condition is WinCondition.PEN and not self.pen_cells:
            problems.append("围栏模式至少需要一格围栏格")
        for pos in self.pen_cells:
            if not self.inside(pos) or self.is_wall(pos):
                problems.append("围栏格不能落在障碍上")
                break
        positions = [cow[0] for cow in self.cows]
        if len(set(positions)) != len(positions):
            problems.append("两头牛不能站在同一格")
        if self.farmer in positions:
            problems.append("农夫和牛不能站在同一格")
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
    bundle = {"version": 2, "game": "The Tamworth Chase", "levels": [payload]}
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
