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

from .core import Simulation
from .levels import parse_level
from .models import GameStatus, Level, Pos

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
        "obstacle_limit": 3,
        "step_limit": 60,
        "s_threshold": 12,
        "a_threshold": 22,
        "b_threshold": 34,
    }
    try:
        return parse_level(payload, source="daily", group="daily")
    except Exception:
        return None


def _candidate_cells(level: Level) -> List[Pos]:
    blocked = set(level.wall_positions)
    blocked.add(level.farmer_start)
    blocked.update(level.cow_positions)
    return [
        (r, c)
        for r in range(level.height)
        for c in range(level.width)
        if (r, c) not in blocked
    ]


def _wins(level: Level, layout: Tuple[Pos, ...]) -> bool:
    sim = Simulation(level, layout, validate=False)
    sim.start()
    guard = level.step_limit + 2
    while sim.status is GameStatus.PLAYING and guard > 0:
        sim.step()
        guard -= 1
    return sim.status is GameStatus.WON


def _solvable(level: Level) -> bool:
    """Bounded search: no bale, one bale, then pairs (fast enough at runtime)."""
    pool = _candidate_cells(level)
    if _wins(level, ()):
        return True
    for pos in pool:
        if _wins(level, (pos,)):
            return True
    for first_index, first in enumerate(pool):
        for second in pool[first_index + 1 :]:
            if _wins(level, (first, second)):
                return True
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
