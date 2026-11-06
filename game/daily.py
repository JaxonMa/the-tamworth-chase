"""Local daily challenge generation.

The daily level is derived from the local calendar date through a fixed seed,
so the same day always produces the same meadow without any server.  Generation
is verified offline with a bounded search so the daily is always winnable; if a
seed produces an unwinnable meadow the next seed is tried deterministically.
"""

from __future__ import annotations

import random
from datetime import date
from typing import List, Optional, Tuple

from .core import step_forward
from .levels import parse_level
from .models import Direction, Level, Pos

DIRECTIONS = ("north", "east", "south", "west")


def date_key(day: Optional[date] = None) -> str:
    return (day or date.today()).isoformat()


def seed_for(day: Optional[date] = None) -> int:
    target = day or date.today()
    return target.year * 10000 + target.month * 100 + target.day


def _candidate(seed: int, level_id: str) -> Optional[Level]:
    rng = random.Random(seed)
    grid = [["." for _ in range(10)] for _ in range(10)]
    for index in range(10):
        grid[0][index] = "#"
        grid[9][index] = "#"
        grid[index][0] = "#"
        grid[index][9] = "#"
    for _ in range(rng.randint(3, 7)):
        row = rng.randint(1, 8)
        col = rng.randint(1, 8)
        grid[row][col] = "#"
        if rng.random() < 0.4:
            grid[min(8, row + 1)][col] = "#"
        if rng.random() < 0.4:
            grid[row][min(8, col + 1)] = "#"
    free = [(r, c) for r in range(1, 9) for c in range(1, 9) if grid[r][c] == "."]
    if len(free) < 58:
        return None
    farmer = rng.choice(free)
    far = [pos for pos in free if abs(pos[0] - farmer[0]) + abs(pos[1] - farmer[1]) >= 4]
    if not far:
        return None
    cow = rng.choice(far)
    rows = [row[:] for row in grid]
    rows[farmer[0]][farmer[1]] = "F"
    rows[cow[0]][cow[1]] = "C"
    payload = {
        "id": level_id,
        "name": "今日牧场",
        "description": "每天一片新的牧场，本地记录你的最好成绩。",
        "hint": "今天的牧场是独一无二的，先观察再动手。",
        "grid": ["".join(row) for row in rows],
        "farmer_facing": rng.choice(DIRECTIONS),
        "cow_facings": [rng.choice(DIRECTIONS)],
        "max_turns": 45,
        "initial_obstacles": 2,
        "prediction_steps": 5,
        "win_condition": "catch",
        "s_threshold": 12,
        "a_threshold": 20,
        "b_threshold": 30,
    }
    try:
        return parse_level(payload, source="daily", group="daily")
    except Exception:
        return None


def _next_cow(pos: Pos, facing: Direction, level: Level) -> Tuple[Pos, Direction]:
    target = step_forward(pos, facing)
    if level.is_inside(target) and not level.is_blocking(target):
        return target, facing
    return pos, facing.clockwise()


def _solvable(level: Level) -> bool:
    """Bounded breadth-first search over the player's five possible actions."""
    farmer = level.farmer_start
    cow = level.cow_positions[0]
    facing = level.cow_facings[0]
    visited = {(farmer, cow, int(facing))}
    frontier: List[Tuple[Pos, Pos, Direction, int]] = [(farmer, cow, facing, 0)]
    moves: List[Optional[Direction]] = [None, *Direction]
    while frontier:
        f_pos, c_pos, c_face, turns = frontier.pop(0)
        if turns >= level.max_turns:
            continue
        for direction in moves:
            target = f_pos if direction is None else step_forward(f_pos, direction)
            if not level.is_inside(target) or level.is_blocking(target):
                continue
            if target == c_pos:
                return True
            new_cow, new_face = _next_cow(c_pos, c_face, level)
            if new_cow == target:
                return True
            state = (target, new_cow, int(new_face))
            if state in visited:
                continue
            visited.add(state)
            frontier.append((target, new_cow, new_face, turns + 1))
    return False


def generate_daily(day: Optional[date] = None, attempts: int = 12) -> Level:
    """Return today's verified meadow, falling back to a campaign level."""
    base = seed_for(day)
    level_id = f"daily_{date_key(day).replace('-', '')}"
    for offset in range(attempts):
        level = _candidate(base + offset * 7919, level_id)
        if level is None:
            continue
        if _solvable(level):
            return level
    from .levels import load_levels

    return load_levels()[0]
