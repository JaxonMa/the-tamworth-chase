"""Deterministic offline solver shared by tests, tools and the editor.

The solver uses the same :class:`game.core.Simulation` and the same five farmer
commands as the game.  It performs a breadth-first search over queued states,
deduplicated by the core state key, so a solved result is a shortest action
sequence.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple

from .core import Simulation
from .models import Action, GameStatus, Level

ACTIONS: Tuple[Action, ...] = (
    Action.TURN_TO_UP,
    Action.TURN_TO_RIGHT,
    Action.TURN_TO_DOWN,
    Action.TURN_TO_LEFT,
    Action.FORWARD,
)


@dataclass(frozen=True)
class SolveResult:
    """Result of one bounded search."""

    status: str
    turns: int = 0
    actions: Tuple[str, ...] = ()
    explored: int = 0
    elapsed: float = 0.0
    reason: str = ""

    @property
    def solved(self) -> bool:
        return self.status == "solved"

    @property
    def is_limit(self) -> bool:
        return self.status == "limit"


def solve_level(
    level: Level,
    max_nodes: int = 400_000,
    *,
    max_depth: Optional[int] = None,
) -> SolveResult:
    """Find a shortest winning command sequence.

    ``status`` is ``solved`` when a win is found, ``unsolvable`` when the whole
    reachable state space has been exhausted, and ``limit`` when the search was
    stopped by ``max_nodes`` or ``max_depth``.
    """
    start_time = time.time()
    start = Simulation(level)
    queue = deque([(start, ())])
    visited = {start.state_key()}
    explored = 0
    while queue and explored < max_nodes:
        sim, path = queue.popleft()
        explored += 1
        for action in ACTIONS:
            probe = sim.clone()
            tick = probe.apply_action(action)
            new_path = path + (action,)
            if tick.status is GameStatus.WON:
                return SolveResult(
                    "solved",
                    probe.turns,
                    tuple(item.value for item in new_path),
                    explored,
                    time.time() - start_time,
                )
            if tick.status.is_finished:
                continue
            if max_depth is not None and len(new_path) >= max_depth:
                continue
            key = probe.state_key()
            if key not in visited:
                visited.add(key)
                queue.append((probe, new_path))
    if queue:
        return SolveResult(
            "limit",
            explored=explored,
            elapsed=time.time() - start_time,
            reason="node limit" if max_depth is None else "depth or node limit",
        )
    return SolveResult(
        "unsolvable",
        explored=explored,
        elapsed=time.time() - start_time,
        reason="state space exhausted",
    )
