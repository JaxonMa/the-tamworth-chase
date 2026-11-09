"""Loading, validation and serialisation of level data.

Levels are plain JSON.  Player facing text is Chinese; keys are English.

The chase-and-escape schema keeps the grid as the main terrain definition and
also understands the optional ``walls`` and ``obstacles`` coordinate lists from
the design document.  ``walls`` coordinates are folded into the grid as fence
tiles; ``obstacles`` are fixed hay bales that block movement and sight.

Missing new fields fall back to sensible defaults so older custom levels still
load.  If an old level has no exit, a deterministic fallback exit is chosen and
marked in ``extra["legacy_exit"]``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .models import (
    COW_CHAR,
    FARMER_CHAR,
    LEGACY_COW_CHARS,
    TILE_CHARS,
    Direction,
    Level,
    TileKind,
    TieBreak,
)
from .paths import project_root

LEVELS_FILE = "levels/levels.json"

_FACING_BY_NAME = {
    "north": Direction.NORTH,
    "east": Direction.EAST,
    "south": Direction.SOUTH,
    "west": Direction.WEST,
    "up": Direction.NORTH,
    "right": Direction.EAST,
    "down": Direction.SOUTH,
    "left": Direction.WEST,
    "n": Direction.NORTH,
    "e": Direction.EAST,
    "s": Direction.SOUTH,
    "w": Direction.WEST,
}

_LEGACY_KEYS = {
    "step_limit",
    "obstacle_limit",
    "initial_obstacles",
    "cow_personalities",
    "apples",
    "items",
    "placed_items",
    "item_counts",
    "win_condition",
    "pen_cells",
    "cow_behavior",
    "tips",
    "practice",
    "goal",
    "tutorial_id",
    "speed",
    "pause",
    "auto_move",
    "sync",
}


class LevelError(ValueError):
    """Raised when level data is malformed.  The message is player facing."""


def _parse_facing(value: Any, default: Direction = Direction.EAST) -> Direction:
    if value is None:
        return default
    if isinstance(value, Direction):
        return value
    if isinstance(value, int):
        if 0 <= value <= 3:
            return Direction(value)
        raise LevelError(f"朝向数值必须在 0 到 3 之间，收到 {value}")
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _FACING_BY_NAME:
            return _FACING_BY_NAME[text]
        if text.isdigit() and 0 <= int(text) <= 3:
            return Direction(int(text))
    raise LevelError(f"无法识别的朝向：{value!r}")


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _parse_tiebreak(value: Any, default: TieBreak = TieBreak.RIGHT) -> TieBreak:
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("left", "l", "0"):
        return TieBreak.LEFT
    if text in ("right", "r", "1"):
        return TieBreak.RIGHT
    raise LevelError(f"无法识别的平局方向：{value!r}")


def parse_level(
    data: Mapping[str, Any],
    *,
    source: str = "main",
    group: str = "main",
    order: int = 0,
) -> Level:
    if not isinstance(data, Mapping):
        raise LevelError("关卡数据必须是一个 JSON 对象")
    level_id = str(data.get("id") or data.get("level_id") or "").strip()
    if not level_id:
        raise LevelError("关卡缺少 id 字段")
    name = str(data.get("name") or data.get("title") or level_id).strip()
    grid = data.get("grid") or data.get("rows")
    if not isinstance(grid, Sequence) or isinstance(grid, (str, bytes)) or not grid:
        raise LevelError(f"关卡 {name} 缺少 grid 网格数据")

    rows: List[str] = [str(row) for row in grid]
    width = len(rows[0])
    if width == 0:
        raise LevelError(f"关卡 {name} 的网格为空")
    for index, row in enumerate(rows):
        if len(row) != width:
            raise LevelError(f"关卡 {name} 第 {index + 1} 行的长度是 {len(row)}，应为 {width}")
    height = len(rows)

    tiles: List[List[TileKind]] = []
    farmer_start: Optional[Tuple[int, int]] = None
    cow_positions: List[Tuple[int, int]] = []

    for r, row in enumerate(rows):
        tile_row: List[TileKind] = []
        for c, char in enumerate(row):
            if char == FARMER_CHAR:
                if farmer_start is not None:
                    raise LevelError(f"关卡 {name} 里出现了多个农夫")
                farmer_start = (r, c)
                tile_row.append(TileKind.GRASS)
            elif char in LEGACY_COW_CHARS:
                cow_positions.append((r, c))
                tile_row.append(TileKind.GRASS)
            elif char in TILE_CHARS:
                tile_row.append(TILE_CHARS[char])
            else:
                raise LevelError(
                    f"关卡 {name} 出现了无法识别的字符 “{char}”（第 {r + 1} 行第 {c + 1} 列）"
                )
        tiles.append(tile_row)

    if farmer_start is None:
        raise LevelError(f"关卡 {name} 里没有农夫（需要一个大写 F）")
    if not cow_positions:
        raise LevelError(f"关卡 {name} 里没有牛（需要一个大写 C）")

    blocked_actors = {farmer_start, *cow_positions}

    # Optional fixed wall coordinates are folded into the grid.
    for item in data.get("walls") or []:
        pos = _parse_pos(item, name)
        if not (0 <= pos[0] < height and 0 <= pos[1] < width):
            raise LevelError(f"关卡 {name} 的墙 {pos} 在牧场外面")
        if pos in blocked_actors:
            raise LevelError(f"关卡 {name} 的墙 {pos} 与角色重叠")
        tiles[pos[0]][pos[1]] = TileKind.FENCE

    obstacles: List[Tuple[int, int]] = []
    for item in data.get("obstacles") or []:
        pos = _parse_pos(item, name)
        if not (0 <= pos[0] < height and 0 <= pos[1] < width):
            raise LevelError(f"关卡 {name} 的固定障碍 {pos} 在牧场外面")
        if pos in blocked_actors or tiles[pos[0]][pos[1]].blocking:
            raise LevelError(f"关卡 {name} 的固定障碍 {pos} 落在不可放置的位置")
        if pos not in obstacles:
            obstacles.append(pos)

    raw_cow_facings = data.get("cow_facings")
    if raw_cow_facings is None:
        cow_facings = [Direction.EAST for _ in cow_positions]
    elif isinstance(raw_cow_facings, Sequence) and not isinstance(raw_cow_facings, str):
        if len(raw_cow_facings) != len(cow_positions):
            raise LevelError(f"关卡 {name} 的牛朝向数量与牛的数量不一致")
        cow_facings = [_parse_facing(item) for item in raw_cow_facings]
    else:
        cow_facings = [_parse_facing(raw_cow_facings) for _ in cow_positions]

    def _int_field(key: str, default: int, minimum: int = 0) -> int:
        value = data.get(key, default)
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise LevelError(f"关卡 {name} 的 {key} 必须是整数") from exc
        if number < minimum:
            raise LevelError(f"关卡 {name} 的 {key} 不能小于 {minimum}")
        return number

    max_turns = _int_field("max_turns", data.get("step_limit", 30), 1)
    prediction_steps = _int_field("prediction_steps", 5, 0)
    if prediction_steps > 20:
        raise LevelError(f"关卡 {name} 的 prediction_steps 不能大于 20")
    exit_sight_range = _int_field("exit_sight_range", -1, -1)
    sight_range = _int_field("sight_range", -1, -1)

    exit_tiebreak = _parse_tiebreak(data.get("exit_tiebreak"), TieBreak.RIGHT)
    flee_tiebreak = _parse_tiebreak(data.get("flee_tiebreak"), TieBreak.RIGHT)

    exits: List[Tuple[int, int]] = []
    for item in data.get("exit_cells") or []:
        pos = _parse_pos(item, name)
        if not (0 <= pos[0] < height and 0 <= pos[1] < width):
            raise LevelError(f"关卡 {name} 的出口 {pos} 在牧场外面")
        if tiles[pos[0]][pos[1]].blocking or pos in obstacles:
            raise LevelError(f"关卡 {name} 的出口 {pos} 落在障碍上")
        if pos == farmer_start:
            raise LevelError(f"关卡 {name} 的农夫不能站在出口 {pos} 上")
        if pos in blocked_actors:
            raise LevelError(f"关卡 {name} 的出口 {pos} 与角色重叠")
        if pos not in exits:
            exits.append(pos)

    legacy_exit = False
    if not exits:
        exit_pos = _fallback_exit(tiles, farmer_start, cow_positions, obstacles)
        if exit_pos is None:
            raise LevelError(f"关卡 {name} 没有可用的出口")
        exits.append(exit_pos)
        legacy_exit = True

    farmer_facing = _parse_facing(
        data.get("fj_start_direction", data.get("farmer_facing")), Direction.NORTH
    )

    s_threshold = _int_field("s_threshold", max(1, max_turns // 3), 1)
    a_threshold = _int_field("a_threshold", max(s_threshold + 1, max_turns // 2), 1)
    b_threshold = _int_field("b_threshold", max(a_threshold + 1, max_turns * 3 // 4), 1)

    hint_raw = data.get("hint_text") or []
    if isinstance(hint_raw, str):
        hint_raw = [hint_raw]
    if not isinstance(hint_raw, Sequence):
        raise LevelError(f"关卡 {name} 的 hint_text 必须是字符串或字符串列表")
    hint_text = tuple(
        str(item).strip() for item in hint_raw if str(item).strip()
    )

    tags = tuple(str(tag) for tag in (data.get("tags") or []))

    known = {
        "id",
        "level_id",
        "name",
        "title",
        "grid",
        "rows",
        "fj_start_direction",
        "farmer_facing",
        "cow_facings",
        "exit_cells",
        "max_turns",
        "prediction_steps",
        "exit_sight_range",
        "sight_range",
        "exit_tiebreak",
        "flee_tiebreak",
        "cows_block_sight",
        "cows_block_each_other",
        "walls",
        "obstacles",
        "s_threshold",
        "a_threshold",
        "b_threshold",
        "hint",
        "description",
        "tags",
        "chapter",
        "learning_objective",
        "hint_text",
    } | _LEGACY_KEYS

    extra = {k: v for k, v in data.items() if k not in known}
    if legacy_exit:
        extra["legacy_exit"] = True

    return Level(
        level_id=level_id,
        name=name,
        width=width,
        height=height,
        tiles=tuple(tuple(row) for row in tiles),
        farmer_start=farmer_start,
        farmer_facing=farmer_facing,
        cow_positions=tuple(cow_positions),
        cow_facings=tuple(cow_facings),
        exit_cells=tuple(exits),
        max_turns=max_turns,
        prediction_steps=prediction_steps,
        exit_sight_range=exit_sight_range,
        sight_range=sight_range,
        exit_tiebreak=exit_tiebreak,
        flee_tiebreak=flee_tiebreak,
        cows_block_sight=_parse_bool(data.get("cows_block_sight"), False),
        cows_block_each_other=_parse_bool(data.get("cows_block_each_other"), False),
        obstacles=tuple(obstacles),
        s_threshold=s_threshold,
        a_threshold=a_threshold,
        b_threshold=b_threshold,
        hint=str(data.get("hint") or ""),
        description=str(data.get("description") or ""),
        order=order,
        group=group,
        source=source,
        chapter=str(data.get("chapter") or group),
        learning_objective=str(data.get("learning_objective") or ""),
        hint_text=hint_text,
        tags=tags,
        extra=extra,
    )


def _fallback_exit(
    tiles: Sequence[Sequence[TileKind]],
    farmer: Tuple[int, int],
    cow_positions: Sequence[Tuple[int, int]],
    obstacles: Sequence[Tuple[int, int]],
) -> Optional[Tuple[int, int]]:
    """Pick a deterministic far corner for legacy levels without exits."""
    height = len(tiles)
    width = len(tiles[0])
    blocked = set(obstacles)
    for r, row in enumerate(tiles):
        for c, tile in enumerate(row):
            if tile.blocking:
                blocked.add((r, c))
    candidates = [
        (r, c)
        for r in range(height)
        for c in range(width)
        if (r, c) not in blocked
        and (r, c) != farmer
        and (r, c) not in cow_positions
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda p: (abs(p[0] - farmer[0]) + abs(p[1] - farmer[1]), p[0], p[1]),
    )


def _parse_pos(value: Any, level_name: str) -> Tuple[int, int]:
    if isinstance(value, Sequence) and len(value) == 2:
        try:
            return (int(value[0]), int(value[1]))
        except (TypeError, ValueError) as exc:
            raise LevelError(f"关卡 {level_name} 的坐标必须是两个整数") from exc
    raise LevelError(f"关卡 {level_name} 的坐标格式不正确：{value!r}")


def load_level_file(path: Path, *, source: str = "main") -> Tuple[Level, ...]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LevelError(f"找不到关卡文件：{Path(path).name}") from exc
    except json.JSONDecodeError as exc:
        raise LevelError(f"关卡文件 {Path(path).name} 不是合法的 JSON：{exc.msg}") from exc

    items = raw.get("levels") if isinstance(raw, Mapping) else None
    if not isinstance(items, list):
        raise LevelError(f"关卡文件 {Path(path).name} 缺少 levels 列表")

    group = str(raw.get("group") or source)
    levels: List[Level] = []
    for index, item in enumerate(items):
        levels.append(parse_level(item, source=source, group=group, order=index))
    return tuple(levels)


def load_levels(path: Optional[Path] = None) -> Tuple[Level, ...]:
    target = Path(path) if path else project_root() / LEVELS_FILE
    return load_level_file(target, source="main")


def level_to_dict(level: Level) -> Dict[str, Any]:
    overlay: Dict[Tuple[int, int], str] = {pos: COW_CHAR for pos in level.cow_positions}
    overlay[level.farmer_start] = FARMER_CHAR

    grid: List[str] = []
    for r in range(level.height):
        chars: List[str] = []
        for c in range(level.width):
            if (r, c) in overlay:
                chars.append(overlay[(r, c)])
            else:
                chars.append(_tile_char(level.tiles[r][c]))
        grid.append("".join(chars))

    payload: Dict[str, Any] = {
        "id": level.level_id,
        "name": level.name,
        "description": level.description,
        "hint": level.hint,
        "grid": grid,
        "fj_start_direction": level.farmer_facing.name.lower(),
        "cow_facings": [f.name.lower() for f in level.cow_facings],
        "exit_cells": [list(pos) for pos in level.exit_cells],
        "max_turns": level.max_turns,
        "prediction_steps": level.prediction_steps,
        "exit_sight_range": level.exit_sight_range,
        "sight_range": level.sight_range,
        "exit_tiebreak": level.exit_tiebreak.value,
        "flee_tiebreak": level.flee_tiebreak.value,
        "cows_block_sight": level.cows_block_sight,
        "cows_block_each_other": level.cows_block_each_other,
        "s_threshold": level.s_threshold,
        "a_threshold": level.a_threshold,
        "b_threshold": level.b_threshold,
    }
    if level.obstacles:
        payload["obstacles"] = [list(pos) for pos in level.obstacles]
    if level.tags:
        payload["tags"] = list(level.tags)
    if level.chapter:
        payload["chapter"] = level.chapter
    if level.learning_objective:
        payload["learning_objective"] = level.learning_objective
    if level.hint_text:
        payload["hint_text"] = list(level.hint_text)
    return payload


def _tile_char(tile: TileKind) -> str:
    for char, kind in TILE_CHARS.items():
        if kind is tile and char not in (FARMER_CHAR, COW_CHAR):
            return char
    return "."
