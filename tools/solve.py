"""Offline level design helper: breadth-first solvability search.

Usage::

    .venv/bin/python tools/solve.py levels/levels.json
    .venv/bin/python tools/solve.py levels/levels.json --level level_01 --json

Cows never react to the farmer, so their poses for every turn can be computed
once up front.  The search then only needs to explore (farmer position, turn)
pairs, which is small even for multi-cow levels.  The tool is a development aid
only; the game never calls it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from game.core import step_forward  # noqa: E402
from game.levels import LevelError, load_level_file  # noqa: E402
from game.models import Cow, Direction, Level, Pos  # noqa: E402

State = Tuple[Pos, Direction]


@dataclass
class SolveResult:
    solved: bool
    turns: int = 0
    actions: Tuple[str, ...] = ()
    obstacles: Tuple[Pos, ...] = ()
    explored: int = 0
    elapsed: float = 0.0


def _cow_timeline(level: Level, obstacles: Sequence[Pos]) -> List[Tuple[State, ...]]:
    blocked = set(level.wall_positions) | set(obstacles)
    cows: List[State] = list(zip(level.cow_positions, level.cow_facings))
    timeline: List[Tuple[State, ...]] = [tuple(cows)]
    for _ in range(level.max_turns):
        updated: List[State] = []
        for index, (pos, facing) in enumerate(cows):
            target = step_forward(pos, facing)
            if target in blocked or not (0 <= target[0] < level.height and 0 <= target[1] < level.width):
                updated.append((pos, facing.clockwise()))
                continue
            if level.cows_block_each_other:
                # Earlier cows have already moved this turn; later cows have not.
                occupied = [p for p, _f in updated] + [
                    p for p, _f in cows[index + 1 :]
                ]
                if target in occupied:
                    updated.append((pos, facing.clockwise()))
                    continue
            updated.append((target, facing))
        cows = updated
        timeline.append(tuple(cows))
    return timeline


def solve(
    level: Level,
    obstacles: Sequence[Pos] = (),
    max_turns: Optional[int] = None,
) -> SolveResult:
    start = time.time()
    obstacles = tuple(obstacles)
    limit = level.max_turns if max_turns is None else min(level.max_turns, max_turns)
    timeline = _cow_timeline(level, obstacles)
    blocked = set(level.wall_positions) | set(obstacles)
    pen = set(level.pen_cells)
    walls = level.wall_positions

    def walkable(pos: Pos) -> bool:
        return 0 <= pos[0] < level.height and 0 <= pos[1] < level.width and pos not in blocked

    def all_penned(cows: Sequence[State]) -> bool:
        return level.is_pen_level and bool(cows) and all(pos in pen for pos, _facing in cows)

    farmer = level.farmer_start
    actions: List[Optional[Direction]] = [None, *Direction]
    queue = deque([(farmer, 0, ())])
    visited = {(farmer, 0)}
    explored = 0
    while queue:
        pos, turn, path = queue.popleft()
        explored += 1
        if turn >= limit:
            continue
        for action in actions:
            target = pos if action is None else step_forward(pos, action)
            if not walkable(target):
                continue
            current = timeline[turn]
            if any(cow_pos == target for cow_pos, _facing in current):
                return SolveResult(True, turn + 1, path + (_name(action),), obstacles, explored, time.time() - start)
            if all_penned(current):
                return SolveResult(True, turn + 1, path + (_name(action),), obstacles, explored, time.time() - start)
            after = timeline[turn + 1]
            if any(cow_pos == target for cow_pos, _facing in after) or all_penned(after):
                return SolveResult(
                    True, turn + 1, path + (_name(action),), obstacles, explored, time.time() - start
                )
            key = (target, turn + 1)
            if key not in visited:
                visited.add(key)
                queue.append((target, turn + 1, path + (_name(action),)))
    return SolveResult(False, 0, (), obstacles, explored, time.time() - start)


def _name(action: Optional[Direction]) -> str:
    return "wait" if action is None else action.name.lower()


def render_solution(level: Level, obstacles: Sequence[Pos]) -> str:
    chars = []
    for r in range(level.height):
        row = []
        for c in range(level.width):
            pos = (r, c)
            if pos == level.farmer_start:
                row.append("F")
            elif pos in level.cow_positions:
                row.append("C")
            elif pos in obstacles:
                row.append("o")
            elif pos in level.pen_cells:
                row.append("p")
            elif pos in level.wall_positions:
                row.append("#")
            else:
                row.append(".")
        chars.append("".join(row))
    return "\n".join(chars)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Search for the shortest solution of a level")
    parser.add_argument("path", nargs="?", default="levels/levels.json")
    parser.add_argument("--level", action="append", default=None, help="level id to solve (repeatable)")
    parser.add_argument("--json", action="store_true", help="print one JSON object per level")
    parser.add_argument("--obstacles", default="", help="semicolon separated row,col pairs")
    args = parser.parse_args(argv)

    obstacles: List[Pos] = []
    for chunk in args.obstacles.split(";"):
        if chunk.strip():
            row, col = chunk.split(",")
            obstacles.append((int(row), int(col)))

    path = Path(args.path)
    try:
        bundle = load_level_file(path, source="main")
    except LevelError as exc:
        print(f"ERROR: {exc}")
        return 2

    wanted = set(args.level or [])
    output: Dict[str, object] = {}
    for level in bundle:
        if wanted and level.level_id not in wanted:
            continue
        result = solve(level, obstacles)
        if args.json:
            output[level.level_id] = {
                "obstacles": [list(p) for p in result.obstacles],
                "turns": result.turns,
                "actions": list(result.actions),
                "status": "won" if result.solved else "unsolved",
            }
            continue
        print(
            f"== {level.level_id} {level.name} "
            f"({level.win_condition.value}, max={level.max_turns}, cows={len(level.cow_positions)})"
        )
        if result.solved:
            print(
                f"  SOLVED in {result.turns} turns ({result.explored} states, "
                f"{result.elapsed:.2f}s)"
            )
            print(render_solution(level, result.obstacles))
            print(f"  actions={list(result.actions)}")
        else:
            print(f"  UNSOLVED ({result.explored} states, {result.elapsed:.2f}s)")
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
