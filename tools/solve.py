"""Offline level design helper: exhaustive solvability search.

Usage::

    .venv/bin/python tools/solve.py levels/levels.json --level level_01 --max-obstacles 3

The tool enumerates obstacle layouts up to the level limit, replays the
simulation for each of them and reports the shortest winning run.  It is a
development aid only; the game never calls it.
"""

from __future__ import annotations

import argparse
import itertools
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from game.core import Simulation  # noqa: E402
from game.levels import LevelError, load_level_file, load_levels  # noqa: E402
from game.models import GameStatus, Level, Pos  # noqa: E402


@dataclass
class SolveResult:
    solved: bool
    steps: int = 0
    obstacles: Tuple[Pos, ...] = ()
    attempts: int = 0
    elapsed: float = 0.0


def candidates(level: Level) -> List[Pos]:
    blocked = set(level.wall_positions)
    blocked.add(level.farmer_start)
    blocked.update(level.cow_positions)
    blocked.update(level.apple_positions)
    cells = [
        (r, c)
        for r in range(level.height)
        for c in range(level.width)
        if (r, c) not in blocked
    ]
    return cells


def run(level: Level, obstacles: Sequence[Pos], limit_steps: Optional[int] = None) -> Tuple[GameStatus, int]:
    sim = Simulation(level, obstacles, validate=False)
    sim.start()
    guard = limit_steps or (level.step_limit + 4)
    while sim.status is GameStatus.PLAYING:
        tick = sim.step()
        if tick is None:
            break
        guard -= 1
        if guard < 0:
            break
    return sim.status, sim.steps


def solve(level: Level, max_obstacles: Optional[int] = None, verbose: bool = True) -> SolveResult:
    start = time.time()
    budget = level.obstacle_limit if max_obstacles is None else max_obstacles
    pool = candidates(level)
    best: Optional[Tuple[int, int, Tuple[Pos, ...]]] = None
    attempts = 0
    for size in range(0, min(budget, len(pool)) + 1):
        found_any = False
        for combo in itertools.combinations(pool, size):
            attempts += 1
            status, steps = run(level, combo)
            if status is GameStatus.WON:
                found_any = True
                if best is None or steps < best[0] or (steps == best[0] and size < best[1]):
                    best = (steps, size, combo)
        if verbose:
            print(f"  obstacles={size}: {attempts} layouts tried, solution={'yes' if found_any else 'no'}")
    elapsed = time.time() - start
    if best is None:
        return SolveResult(False, 0, (), attempts, elapsed)
    return SolveResult(True, best[0], best[2], attempts, elapsed)


def render_solution(level: Level, obstacles: Sequence[Pos]) -> str:
    """ASCII rendering of the board with the winning obstacle layout."""
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
    parser.add_argument("--max-obstacles", type=int, default=None)
    args = parser.parse_args(argv)

    path = Path(args.path)
    try:
        bundle = load_level_file(path, source="main")
    except LevelError as exc:
        print(f"ERROR: {exc}")
        return 2

    wanted = set(args.level or [])
    for level in bundle:
        if wanted and level.level_id not in wanted:
            continue
        print(f"== {level.level_id} {level.name} ({level.width}x{level.height}, "
              f"obstacles<={level.obstacle_limit}, steps<={level.step_limit})")
        result = solve(level, args.max_obstacles)
        if result.solved:
            print(f"  SOLVED in {result.steps} steps using {len(result.obstacles)} obstacles "
                  f"({result.attempts} layouts, {result.elapsed:.1f}s)")
            print(render_solution(level, result.obstacles))
            print(f"  obstacles={list(result.obstacles)}")
        else:
            print(f"  UNSOLVED ({result.attempts} layouts, {result.elapsed:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
