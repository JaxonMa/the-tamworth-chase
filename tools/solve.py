"""Offline solver for the tank-driving, exit-escape chase.

The tests, the editor export check and the failure dialog's solution playback
all call the shared :mod:`game.solver`; this CLI simply exposes the same search.

Usage::

    .venv/bin/python tools/solve.py levels/levels.json
    .venv/bin/python tools/solve.py levels/levels.json --level level_01 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from game.levels import LevelError, load_level_file  # noqa: E402
from game.models import Level  # noqa: E402
from game.solver import solve_level  # noqa: E402


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
    parser = argparse.ArgumentParser(description="Search for a shortest escape-chase solution")
    parser.add_argument("path", nargs="?", default="levels/levels.json")
    parser.add_argument("--level", action="append", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-nodes", type=int, default=400_000)
    parser.add_argument("--max-seconds", type=float, default=None)
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
        result = solve_level(
            level,
            args.max_nodes,
            max_seconds=args.max_seconds,
        )
        if args.json:
            output[level.level_id] = {
                "turns": result.turns,
                "actions": list(result.actions),
                "status": "won" if result.solved else "unsolved",
                "solver_status": result.status,
                "explored": result.explored,
                "reason": result.reason,
            }
            continue
        print(
            f"== {level.level_id} {level.name} "
            f"(cows={len(level.cow_positions)}, max={level.max_turns}, "
            f"exit={list(level.exit_cells)})"
        )
        if result.solved:
            print(
                f"  SOLVED in {result.turns} turns "
                f"({result.explored} states, {result.elapsed:.2f}s)"
            )
            print(render_solution(level))
            print(f"  actions={list(result.actions)}")
        else:
            print(f"  {result.status.upper()} ({result.explored} states, {result.reason})")
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
