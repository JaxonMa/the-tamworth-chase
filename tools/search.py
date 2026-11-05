"""Development helper: search combined hay-bale + item layouts.

Extends the exhaustive solver with item placement so tutorial and challenge
levels that use apples, horns and the like can be verified offline.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from game.core import Simulation
from game.models import GameStatus, ItemKind, Level, Pos


@dataclass
class LayoutResult:
    solved: bool
    steps: int = 0
    obstacles: Tuple[Pos, ...] = ()
    items: Tuple[Tuple[ItemKind, Pos], ...] = ()
    tries: int = 0
    elapsed: float = 0.0


def _candidates(level: Level) -> List[Pos]:
    blocked = set(level.wall_positions)
    blocked.add(level.farmer_start)
    blocked.update(level.cow_positions)
    blocked.update(item.pos for item in level.items)
    return [
        (r, c)
        for r in range(level.height)
        for c in range(level.width)
        if (r, c) not in blocked
    ]


def _run(level: Level, obstacles: Sequence[Pos], items: Sequence[Tuple[ItemKind, Pos]]) -> Tuple[GameStatus, int]:
    sim = Simulation(level, obstacles)
    for kind, pos in items:
        if not sim.place_item(kind, pos).ok:
            return GameStatus.READY, 0
    sim.start()
    guard = level.step_limit + 4
    while sim.status is GameStatus.PLAYING and guard > 0:
        sim.step()
        guard -= 1
    return sim.status, sim.steps


def search(
    level: Level,
    max_obstacles: Optional[int] = None,
    *,
    extra_tools: Sequence[ItemKind] = (),
    max_tries: int = 3_000_000,
) -> LayoutResult:
    """Brute-force obstacle and item layouts, shortest win first."""
    start = time.time()
    budget = level.obstacle_limit if max_obstacles is None else max_obstacles
    pool = _candidates(level)
    tool_counts = dict(level.item_counts)
    tries = 0
    best: Optional[Tuple[int, int]] = None
    best_layout: Tuple[Tuple[Pos, ...], Tuple[Tuple[ItemKind, Pos], ...]] = ((), ())

    obstacle_sets: List[Tuple[Pos, ...]] = []
    for size in range(0, min(budget, len(pool)) + 1):
        for combo in itertools.combinations(pool, size):
            obstacle_sets.append(combo)
            tries += 1
            if tries > max_tries:
                break
        if tries > max_tries:
            break

    for obstacles in obstacle_sets:
        used = set(obstacles)
        free = [pos for pos in pool if pos not in used]
        item_choices: List[Tuple[ItemKind, Pos]] = []
        per_kind: List[Tuple[ItemKind, int]] = [
            (ItemKind(kind), count) for kind, count in tool_counts.items() if count > 0
        ]
        options: List[List[Tuple[ItemKind, Pos]]] = []
        for kind, count in per_kind:
            combos = list(itertools.combinations(free, count))
            options.append([tuple((kind, pos) for pos in combo) for combo in combos])
        for selection in itertools.product(*options) if options else [()]:
            items = [entry for part in selection for entry in part]
            status, steps = _run(level, obstacles, items)
            tries += 1
            if status is GameStatus.WON and (best is None or steps < best[0]):
                best = (steps, len(obstacles))
                best_layout = (obstacles, tuple(items))
    elapsed = time.time() - start
    if best is None:
        return LayoutResult(False, 0, (), (), tries, elapsed)
    return LayoutResult(True, best[0], best_layout[0], best_layout[1], tries, elapsed)
