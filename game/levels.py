"""Loading, validation and serialisation of level data.

Levels are plain JSON so that the editor, the tutorial chapter files and the
main campaign all share a single schema.  Player facing text inside the JSON is
Chinese; every internal key is English.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .models import (
    COW_CHARS,
    FARMER_CHAR,
    TILE_CHARS,
    CowPersonality,
    Direction,
    Level,
    PERSONALITY_BY_CHAR,
    TileKind,
    Tip,
)
from .paths import project_root

LEVELS_FILE = "levels/levels.json"
TUTORIAL_FILES = {
    "basics": "tutorials/basics.json",
    "advanced": "tutorials/advanced.json",
    "editor": "tutorials/editor.json",
}

_FACING_BY_NAME = {
    "north": Direction.NORTH,
    "east": Direction.EAST,
    "south": Direction.SOUTH,
    "west": Direction.WEST,
    "n": Direction.NORTH,
    "e": Direction.EAST,
    "s": Direction.SOUTH,
    "w": Direction.WEST,
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


def parse_level(
    data: Mapping[str, Any],
    *,
    source: str = "main",
    group: str = "main",
    order: int = 0,
    tutorial_id: str = "",
) -> Level:
    """Build a :class:`Level` from a decoded JSON mapping."""
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
            raise LevelError(
                f"关卡 {name} 第 {index + 1} 行的长度是 {len(row)}，应为 {width}"
            )
    height = len(rows)

    tiles: List[List[TileKind]] = []
    farmer_start: Optional[Tuple[int, int]] = None
    cows: List[Tuple[Tuple[int, int], CowPersonality]] = []

    for r, row in enumerate(rows):
        tile_row: List[TileKind] = []
        for c, char in enumerate(row):
            if char == FARMER_CHAR:
                if farmer_start is not None:
                    raise LevelError(f"关卡 {name} 里出现了多个农夫")
                farmer_start = (r, c)
                tile_row.append(TileKind.GRASS)
            elif char in COW_CHARS:
                cows.append(((r, c), PERSONALITY_BY_CHAR[char]))
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
    if not cows:
        raise LevelError(f"关卡 {name} 里没有牛（需要一个大写 C）")

    # Facing data may be a single value or a list matching the cow order.
    raw_cow_facings = data.get("cow_facings")
    if raw_cow_facings is None:
        cow_facings = [Direction.EAST for _ in cows]
    elif isinstance(raw_cow_facings, Sequence) and not isinstance(raw_cow_facings, str):
        if len(raw_cow_facings) != len(cows):
            raise LevelError(f"关卡 {name} 的牛朝向数量与牛的数量不一致")
        cow_facings = [_parse_facing(item) for item in raw_cow_facings]
    else:
        cow_facings = [_parse_facing(raw_cow_facings) for _ in cows]

    raw_personalities = data.get("cow_personalities")
    personalities: List[CowPersonality] = [p for _, p in cows]
    if raw_personalities is not None:
        if not isinstance(raw_personalities, Sequence) or isinstance(raw_personalities, str):
            raise LevelError(f"关卡 {name} 的 cow_personalities 必须是列表")
        if len(raw_personalities) != len(cows):
            raise LevelError(f"关卡 {name} 的牛性格数量与牛的数量不一致")
        for index, item in enumerate(raw_personalities):
            try:
                personalities[index] = CowPersonality(str(item))
            except ValueError as exc:
                raise LevelError(f"关卡 {name} 出现了未知的牛性格：{item}") from exc

    apples: List[Tuple[int, int]] = []
    for item in data.get("apples") or []:
        pos = _parse_pos(item, name)
        apples.append(pos)

    def _int_field(key: str, default: int, minimum: int = 0) -> int:
        value = data.get(key, default)
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise LevelError(f"关卡 {name} 的 {key} 必须是整数") from exc
        if number < minimum:
            raise LevelError(f"关卡 {name} 的 {key} 不能小于 {minimum}")
        return number

    obstacle_limit = _int_field("obstacle_limit", 3, 0)
    step_limit = _int_field("step_limit", 60, 1)
    s_threshold = _int_field("s_threshold", max(1, step_limit // 3), 1)
    a_threshold = _int_field("a_threshold", max(s_threshold + 1, step_limit // 2), 1)
    b_threshold = _int_field("b_threshold", max(a_threshold + 1, step_limit * 3 // 4), 1)

    tips_raw = data.get("tips") or []
    tips: List[Tip] = []
    for item in tips_raw:
        if not isinstance(item, Mapping):
            raise LevelError(f"关卡 {name} 的提示格式不正确")
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        tips.append(Tip(trigger=str(item.get("trigger") or "start"), text=text))

    item_counts: Dict[str, int] = {}
    raw_items = data.get("items") or {}
    if isinstance(raw_items, Mapping):
        for key, value in raw_items.items():
            try:
                count = int(value)
            except (TypeError, ValueError) as exc:
                raise LevelError(f"关卡 {name} 的道具数量必须是整数") from exc
            if count > 0:
                item_counts[str(key)] = count

    tags = tuple(str(tag) for tag in (data.get("tags") or []))

    return Level(
        level_id=level_id,
        name=name,
        width=width,
        height=height,
        tiles=tuple(tuple(row) for row in tiles),
        farmer_start=farmer_start,
        farmer_facing=_parse_facing(data.get("farmer_facing"), Direction.EAST),
        cow_positions=tuple(pos for pos, _ in cows),
        cow_facings=tuple(cow_facings),
        cow_personalities=tuple(personalities),
        obstacle_limit=obstacle_limit,
        step_limit=step_limit,
        s_threshold=s_threshold,
        a_threshold=a_threshold,
        b_threshold=b_threshold,
        hint=str(data.get("hint") or ""),
        description=str(data.get("description") or ""),
        order=order,
        group=group,
        source=source,
        tags=tags,
        tutorial_id=tutorial_id,
        goal_text=str(data.get("goal") or ""),
        tips=tuple(tips),
        practice_text=str(data.get("practice") or ""),
        apple_positions=tuple(apples),
        item_counts=item_counts,
        extra={
            k: v
            for k, v in data.items()
            if k
            not in {
                "id",
                "level_id",
                "name",
                "title",
                "grid",
                "rows",
                "obstacle_limit",
                "step_limit",
                "s_threshold",
                "a_threshold",
                "b_threshold",
                "hint",
                "description",
                "tags",
                "tips",
                "goal",
                "practice",
                "apples",
                "items",
                "cow_facings",
                "cow_personalities",
                "farmer_facing",
            }
        },
    )


def _parse_pos(value: Any, level_name: str) -> Tuple[int, int]:
    if isinstance(value, Sequence) and len(value) == 2:
        try:
            return (int(value[0]), int(value[1]))
        except (TypeError, ValueError) as exc:
            raise LevelError(f"关卡 {level_name} 的坐标必须是两个整数") from exc
    raise LevelError(f"关卡 {level_name} 的坐标格式不正确：{value!r}")


def load_level_file(path: Path, *, source: str = "main") -> Tuple[Level, ...]:
    """Load a level bundle from ``path`` (``{"levels": [...]}``)."""
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
    """Load the main campaign."""
    target = Path(path) if path else project_root() / LEVELS_FILE
    return load_level_file(target, source="main")


def load_tutorials(
    chapter: Optional[str] = None, path: Optional[Path] = None
) -> Dict[str, Tuple[Level, ...]]:
    """Load one or all tutorial chapters, keyed by chapter id."""
    chapters = [chapter] if chapter else list(TUTORIAL_FILES)
    result: Dict[str, Tuple[Level, ...]] = {}
    for key in chapters:
        target = Path(path) if path and chapter else project_root() / TUTORIAL_FILES[key]
        result[key] = load_level_file(target, source="tutorial")
    return result


def level_to_dict(level: Level) -> Dict[str, Any]:
    """Serialise a level back to the JSON schema (used by the editor)."""
    overlay: Dict[Tuple[int, int], str] = {}
    for index, pos in enumerate(level.cow_positions):
        char = {v: k for k, v in PERSONALITY_BY_CHAR.items()}[level.cow_personalities[index]]
        overlay[pos] = char
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
        "farmer_facing": level.farmer_facing.name.lower(),
        "cow_facings": [f.name.lower() for f in level.cow_facings],
        "cow_personalities": [p.value for p in level.cow_personalities],
        "obstacle_limit": level.obstacle_limit,
        "step_limit": level.step_limit,
        "s_threshold": level.s_threshold,
        "a_threshold": level.a_threshold,
        "b_threshold": level.b_threshold,
    }
    if level.apple_positions:
        payload["apples"] = [list(pos) for pos in level.apple_positions]
    if level.item_counts:
        payload["items"] = dict(level.item_counts)
    if level.tags:
        payload["tags"] = list(level.tags)
    if level.tips:
        payload["tips"] = [{"trigger": tip.trigger, "text": tip.text} for tip in level.tips]
    if level.goal_text:
        payload["goal"] = level.goal_text
    if level.practice_text:
        payload["practice"] = level.practice_text
    return payload


def _tile_char(tile: TileKind) -> str:
    for char, kind in TILE_CHARS.items():
        if kind is tile and char not in (FARMER_CHAR,) + COW_CHARS:
            return char
    return "."
