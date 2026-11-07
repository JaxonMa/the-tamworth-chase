"""Local daily challenge generation for the exit-escape chase.

The daily meadow is derived from the local calendar date through a fixed seed,
so the same day always produces the same board without any server.  A bounded
search confirms that the farmer can catch every cow before it escapes; if a seed
produces an unwinnable meadow, the next deterministic seed is tried.
"""

from __future__ import annotations

import random
from collections import deque
from datetime import date
from typing import Optional

from .core import Simulation
from .levels import parse_level
from .models import Action, GameStatus, Level

DIRECTIONS = ("up", "right", "down", "left")


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
    for _ in range(rng.randint(3, 6)):
        row = rng.randint(1, 8)
        col = rng.randint(1, 8)
        grid[row][col] = "#"
        if rng.random() < 0.35:
            grid[min(8, row + 1)][col] = "#"
    free = [(r, c) for r in range(1, 9) for c in range(1, 9) if grid[r][c] == "."]
    if len(free) < 55:
        return None
    farmer = rng.choice(free)
    far = [pos for pos in free if abs(pos[0] - farmer[0]) + abs(pos[1] - farmer[1]) >= 5]
    if not far:
        return None
    cow = rng.choice(far)
    exits = [
        pos
        for pos in free
        if pos not in (farmer, cow)
        and abs(pos[0] - cow[0]) + abs(pos[1] - cow[1]) >= 2
    ]
    if not exits:
        return None
    exit_cell = rng.choice(exits)
    rows = [row[:] for row in grid]
    rows[farmer[0]][farmer[1]] = "F"
    rows[cow[0]][cow[1]] = "C"
    payload = {
        "id": level_id,
        "name": "今日牧场",
        "description": "每天一片新的牧场，本地记录你的最好成绩。",
        "hint": "先看出口在哪里，再决定从哪条路拦牛。",
        "grid": ["".join(row) for row in rows],
        "fj_start_direction": rng.choice(DIRECTIONS),
        "cow_facings": [rng.choice(DIRECTIONS)],
        "cow_behavior": "seek_exit",
        "exit_cells": [list(exit_cell)],
        "max_turns": 50,
        "prediction_steps": 5,
        "sight_range": -1,
        "exit_sight_range": -1,
        "s_threshold": 12,
        "a_threshold": 20,
        "b_threshold": 30,
    }
    try:
        return parse_level(payload, source="daily", group="daily")
    except Exception:
        return None


def _solvable(level: Level, max_nodes: int = 24_000) -> bool:
    """Bounded breadth-first search over the four tank actions."""
    start = Simulation(level)
    queue = deque([start])
    visited = {start.state_key()}
    nodes = 0
    actions = (Action.FORWARD, Action.TURN_LEFT, Action.TURN_RIGHT, Action.WAIT)
    while queue and nodes < max_nodes:
        sim = queue.popleft()
        nodes += 1
        for action in actions:
            probe = sim.clone()
            tick = probe.apply_action(action)
            if tick.status is GameStatus.WON:
                return True
            if tick.status.is_finished:
                continue
            key = probe.state_key()
            if key not in visited:
                visited.add(key)
                queue.append(probe)
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
