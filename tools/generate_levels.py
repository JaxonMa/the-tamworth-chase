"""Development helper: search for level layouts by difficulty tier.

The generator builds random-but-structured wall layouts, then probes them with
the exhaustive solver to find layouts that need a specific number of player
placed obstacles.  Output is written as JSON for manual curation.

Usage::

    .venv/bin/python tools/generate_levels.py --count 160 --out /tmp/gen.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from multiprocessing import Pool
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from game.core import Simulation  # noqa: E402
from game.levels import parse_level  # noqa: E402
from game.models import Direction, GameStatus, Level, Pos  # noqa: E402
from tools.solve import candidates, run, solve  # noqa: E402

SIZE = 10
STYLES = ("mirror", "pillars", "rooms", "corridor", "scatter")


def _blank() -> List[List[str]]:
    grid = [["." for _ in range(SIZE)] for _ in range(SIZE)]
    for i in range(SIZE):
        grid[0][i] = "#"
        grid[SIZE - 1][i] = "#"
        grid[i][0] = "#"
        grid[i][SIZE - 1] = "#"
    return grid


def _paint_block(grid: List[List[str]], r: int, c: int) -> None:
    if 1 <= r <= SIZE - 2 and 1 <= c <= SIZE - 2:
        grid[r][c] = "#"


def _mirror(grid: List[List[str]]) -> None:
    for r in range(SIZE):
        for c in range(1, SIZE // 2):
            if grid[r][c] != "#":
                continue
            grid[r][SIZE - 1 - c] = "#"
        for c in range(SIZE // 2 + 1, SIZE - 1):
            if grid[r][SIZE - 1 - c] == "#":
                grid[r][c] = "#"


def make_grid(rng: random.Random, style: str) -> List[List[str]]:
    grid = _blank()
    if style == "mirror":
        for _ in range(rng.randint(4, 7)):
            r = rng.randint(1, SIZE - 2)
            c = rng.randint(1, SIZE // 2)
            grid[r][c] = "#"
            if rng.random() < 0.45:
                grid[r][min(c + 1, SIZE - 2)] = "#"
        _mirror(grid)
    elif style == "pillars":
        for _ in range(rng.randint(3, 5)):
            r = rng.randint(1, SIZE - 3)
            c = rng.randint(1, SIZE - 3)
            for dr in range(rng.randint(1, 2)):
                for dc in range(rng.randint(1, 2)):
                    grid[r + dr][c + dc] = "#"
        _mirror(grid)
    elif style == "rooms":
        for _ in range(rng.randint(1, 2)):
            r0 = rng.randint(1, 4)
            c0 = rng.randint(1, 4)
            h = rng.randint(3, 5)
            w = rng.randint(3, 5)
            r1 = min(r0 + h, SIZE - 2)
            c1 = min(c0 + w, SIZE - 2)
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    if r in (r0, r1) or c in (c0, c1):
                        grid[r][c] = "#"
            # carve one or two doorways
            for _ in range(rng.randint(1, 2)):
                if rng.random() < 0.5:
                    grid[rng.choice([r0, r1])][rng.randint(c0 + 1, max(c0 + 1, c1 - 1))] = "."
                else:
                    grid[rng.randint(r0 + 1, max(r0 + 1, r1 - 1))][rng.choice([c0, c1])] = "."
    elif style == "corridor":
        for _ in range(rng.randint(3, 5)):
            horizontal = rng.random() < 0.5
            r = rng.randint(1, SIZE - 2)
            c = rng.randint(1, SIZE - 2)
            length = rng.randint(2, 4)
            for i in range(length):
                if horizontal:
                    _paint_block(grid, r, c + i)
                else:
                    _paint_block(grid, r + i, c)
        if rng.random() < 0.5:
            _mirror(grid)
    else:  # scatter
        for _ in range(rng.randint(8, 14)):
            r = rng.randint(1, SIZE - 2)
            c = rng.randint(1, SIZE - 2)
            grid[r][c] = "#"

    return grid


def free_cells(grid: Sequence[Sequence[str]]) -> List[Tuple[int, int]]:
    return [(r, c) for r in range(SIZE) for c in range(SIZE) if grid[r][c] == "."]


def connected(grid: Sequence[Sequence[str]], start: Pos, goal: Pos) -> bool:
    seen = {start}
    stack = [start]
    while stack:
        r, c = stack.pop()
        if (r, c) == goal:
            return True
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < SIZE and 0 <= nc < SIZE and (nr, nc) not in seen and grid[nr][nc] != "#":
                seen.add((nr, nc))
                stack.append((nr, nc))
    return False


def build_candidate(seed: int) -> Optional[Dict[str, object]]:
    rng = random.Random(seed)
    style = STYLES[seed % len(STYLES)]
    grid = make_grid(rng, style)
    cells = free_cells(grid)
    if len(cells) < 20:
        return None
    farmer = rng.choice(cells)
    far = [p for p in cells if abs(p[0] - farmer[0]) + abs(p[1] - farmer[1]) >= 4]
    if not far:
        return None
    cow = rng.choice(far)
    if not connected(grid, farmer, cow):
        return None
    rows = ["".join(row) for row in grid]
    chars = [list(row) for row in rows]
    chars[farmer[0]][farmer[1]] = "F"
    chars[cow[0]][cow[1]] = "C"
    rows = ["".join(row) for row in chars]
    payload = {
        "id": f"gen_{seed}",
        "name": f"gen_{seed}",
        "grid": rows,
        "obstacle_limit": 3,
        "step_limit": 80,
        "farmer_facing": rng.choice(["north", "east", "south", "west"]),
        "cow_facings": [rng.choice(["north", "east", "south", "west"])],
    }
    return {"seed": seed, "style": style, "payload": payload}


def evaluate(item: Dict[str, object]) -> Optional[Dict[str, object]]:
    payload = item["payload"]  # type: ignore[index]
    level = parse_level(payload, source="generated")
    zero_status, zero_steps = run(level, ())
    if zero_status is GameStatus.WON:
        return None
    one = solve(level, 1, verbose=False)
    if one.solved:
        tier = "easy"
        if one.steps < 6:
            return None
        return {
            **item,
            "tier": tier,
            "min_steps": one.steps,
            "best_obstacles": len(one.obstacles),
            "solution": [list(p) for p in one.obstacles],
        }
    two = solve(level, 2, verbose=False)
    if two.solved:
        if two.steps < 8:
            return None
        return {
            **item,
            "tier": "medium",
            "min_steps": two.steps,
            "best_obstacles": len(two.obstacles),
            "solution": [list(p) for p in two.obstacles],
        }
    return {**item, "tier": "pending", "min_steps": 0, "best_obstacles": 0, "solution": []}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=120)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--out", default="/tmp/generated_levels.json")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)

    candidates = [c for c in (build_candidate(s) for s in range(args.start, args.start + args.count)) if c]
    print(f"built {len(candidates)} candidate layouts", flush=True)
    results: List[Dict[str, object]] = []
    with Pool(args.workers) as pool:
        for index, item in enumerate(pool.imap_unordered(evaluate, candidates, chunksize=1), 1):
            if item:
                results.append(item)
            if index % 10 == 0:
                print(f"  evaluated {index}/{len(candidates)}", flush=True)

    by_tier: Dict[str, List[Dict[str, object]]] = {"easy": [], "medium": [], "pending": []}
    for item in results:
        by_tier[str(item["tier"])].append(item)
    for tier, items in by_tier.items():
        print(f"{tier}: {len(items)}")
    Path(args.out).write_text(json.dumps(by_tier, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
