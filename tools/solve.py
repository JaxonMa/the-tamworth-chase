"""Offline solver for the tank-driving, exit-escape chase.

The game itself never imports this module.  It explores the four farmer actions
with a breadth-first search and reports the shortest winning order sequence.

Usage::

    .venv/bin/python tools/solve.py levels/levels.json
    .venv/bin/python tools/solve.py levels/levels.json --level level_01 --json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from game.core import Simulation  # noqa: E402
from game.levels import LevelError, load_level_file  # noqa: E402
from game.models import Action, GameStatus, Level  # noqa: E402


@dataclass
class SolveResult:
    solved: bool
    turns: int = 0
    actions: Tuple[str, ...] = ()
    explored: int = 0
    elapsed: float = 0.0


def solve(level: Level, max_nodes: int = 400_000) -> SolveResult:
    start_time = time.time()
    start = Simulation(level)
    actions = (Action.FORWARD, Action.TURN_LEFT, Action.TURN_RIGHT, Action.WAIT)
    queue = deque([(start, ())])
    visited = {start.state_key()}
    explored = 0
    while queue and explored < max_nodes:
        sim, path = queue.popleft()
        explored += 1
        for action in actions:
            probe = sim.clone()
            tick = probe.apply_action(action)
            new_path = path + (action,)
            if tick.status is GameStatus.WON:
                return SolveResult(
                    True, probe.turns, tuple(a.value for a in new_path), explored, time.time() - start_time
                )
            if tick.status.is_finished:
                continue
            key = probe.state_key()
            if key not in visited:
                visited.add(key)
                queue.append((probe, new_path))
    return SolveResult(False, 0, (), explored, time.time() - start_time)


def render_solution(level: Level) -> str:
    chars = []
    for r in range(level.height):
        row = []
        for c in range(level.width):
            pos = (r, c)
            if pos == level.farmer_start:
                row.append("F")
            elif pos in level.cow_positions:
                row.append("C")
            elif pos in level.exit_cells:
                row.append("E")
            elif pos in level.obstacles:
                row.append("o")
            elif pos in level.wall_positions:
                row.append("#")
            else:
                row.append(".")
        chars.append("".join(row))
    return "\n".join(chars)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Search for the shortest escape-chase solution")
    parser.add_argument("path", nargs="?", default="levels/levels.json")
    parser.add_argument("--level", action="append", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-nodes", type=int, default=400_000)
    args = parser.parse_args(argv)

    path = Path(args.path)
    try:
        bundle = load_level_file(path)
    except LevelError as exc:
        print(f"ERROR: {exc}")
        return 2
    wanted = set(args.level or [])
    output: Dict[str, object] = {}
    for level in bundle:
        if wanted and level.level_id not in wanted:
            continue
        result = solve(level, args.max_nodes)
        if args.json:
            output[level.level_id] = {
                "turns": result.turns,
                "actions": list(result.actions),
                "status": "won" if result.solved else "unsolved",
            }
            continue
        print(
            f"== {level.level_id} {level.name} "
            f"(cows={len(level.cow_positions)}, max={level.max_turns}, "
            f"exit={list(level.exit_cells)})"
        )
        if result.solved:
            print(f"  SOLVED in {result.turns} turns ({result.explored} states, {result.elapsed:.2f}s)")
            print(render_solution(level))
            print(f"  actions={list(result.actions)}")
        else:
            print(f"  UNSOLVED ({result.explored} states, {result.elapsed:.2f}s)")
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
