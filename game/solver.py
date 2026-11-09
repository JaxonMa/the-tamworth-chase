"""Deterministic offline solver shared by playback, tests, tools and the editor.

The solver uses the same :class:`game.core.Simulation` and the same five farmer
commands as the game.  It performs a breadth-first search over queued states,
deduplicated by the core state key, so a solved result is a shortest action
sequence.  :func:`solve_level_cached` adds a bounded cache for the failure
dialog; the key includes the rule version and rule-relevant level data.
"""

from __future__ import annotations

import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .core import Simulation
from .models import Action, GameStatus, Level

ACTIONS: Tuple[Action, ...] = (
    Action.TURN_TO_UP,
    Action.TURN_TO_RIGHT,
    Action.TURN_TO_DOWN,
    Action.TURN_TO_LEFT,
    Action.FORWARD,
)

#: Bump this whenever a core rule changes in a way that can alter a solution.
#: The playback cache includes it together with the level's rule-relevant data.
RULES_VERSION = 7

_CACHE_LIMIT = 32
_CACHE: "OrderedDict[tuple, SolveResult]" = OrderedDict()
_CACHE_HITS = 0
_CACHE_MISSES = 0


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


def level_signature(level: Level) -> tuple:
    """Rule-relevant, hashable representation of one level's data."""
    return (
        level.level_id,
        level.name,
        level.width,
        level.height,
        level.rows,
        level.farmer_start,
        int(level.farmer_facing),
        tuple(level.cow_positions),
        tuple(int(facing) for facing in level.cow_facings),
        tuple(level.exit_cells),
        tuple(level.obstacles),
        level.max_turns,
        level.sight_range,
        level.exit_sight_range,
        level.exit_tiebreak.value,
        level.flee_tiebreak.value,
        level.cows_block_sight,
        level.cows_block_each_other,
    )


def solve_level(
    level: Level,
    max_nodes: int = 400_000,
    *,
    max_depth: Optional[int] = None,
    max_seconds: Optional[float] = None,
) -> SolveResult:
    """Find a shortest winning command sequence.

    ``status`` is ``solved`` when a win is found, ``unsolvable`` when the whole
    reachable state space has been exhausted, and ``limit`` when the search was
    stopped by ``max_nodes``, ``max_depth`` or the wall-clock ``max_seconds``.
    """
    start_time = time.monotonic()
    if max_seconds is not None and max_seconds <= 0:
        return SolveResult(
            "limit",
            elapsed=0.0,
            reason="time limit",
        )
    deadline = None if max_seconds is None else start_time + max_seconds
    start = Simulation(level)
    queue = deque([(start, ())])
    visited = {start.state_key()}
    explored = 0
    depth_truncated = False
    timed_out = False
    while queue and explored < max_nodes:
        if deadline is not None and explored % 64 == 0 and time.monotonic() >= deadline:
            timed_out = True
            break
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
                    time.monotonic() - start_time,
                )
            if tick.status.is_finished:
                continue
            if max_depth is not None and len(new_path) >= max_depth:
                depth_truncated = True
                continue
            key = probe.state_key()
            if key not in visited:
                visited.add(key)
                queue.append((probe, new_path))
    if queue or depth_truncated or timed_out:
        reasons = []
        if explored >= max_nodes:
            reasons.append("node limit")
        if max_depth is not None:
            reasons.append("depth limit")
        if timed_out:
            reasons.append("time limit")
        return SolveResult(
            "limit",
            explored=explored,
            elapsed=time.monotonic() - start_time,
            reason=", ".join(reasons) or "search limit",
        )
    return SolveResult(
        "unsolvable",
        explored=explored,
        elapsed=time.monotonic() - start_time,
        reason="state space exhausted",
    )


def _cache_key(
    level: Level,
    max_nodes: int,
    max_depth: Optional[int],
    max_seconds: Optional[float],
) -> tuple:
    return (
        RULES_VERSION,
        level_signature(level),
        int(max_nodes),
        max_depth,
        max_seconds,
    )


def solve_level_cached(
    level: Level,
    max_nodes: int = 400_000,
    *,
    max_depth: Optional[int] = None,
    max_seconds: Optional[float] = None,
) -> SolveResult:
    """Return a cached solve, invalidated by level data or rule version.

    Solved and exhausted searches are cached, so a failure dialog that asks
    again returns immediately.  A resource-limited search is deliberately not
    cached: a timeout can be transient and the player should be able to retry.
    """
    global _CACHE_HITS, _CACHE_MISSES
    key = _cache_key(level, max_nodes, max_depth, max_seconds)
    cached = _CACHE.get(key)
    if cached is not None:
        _CACHE_HITS += 1
        _CACHE.move_to_end(key)
        return cached
    _CACHE_MISSES += 1
    result = solve_level(
        level,
        max_nodes=max_nodes,
        max_depth=max_depth,
        max_seconds=max_seconds,
    )
    if result.status != "limit":
        _CACHE[key] = result
        if len(_CACHE) > _CACHE_LIMIT:
            _CACHE.popitem(last=False)
    return result


def solver_cache_info() -> Dict[str, int]:
    """Small observable snapshot used by tests and diagnostics."""
    return {
        "size": len(_CACHE),
        "hits": _CACHE_HITS,
        "misses": _CACHE_MISSES,
    }


def clear_solver_cache() -> None:
    """Drop cached solutions and reset cache counters."""
    global _CACHE_HITS, _CACHE_MISSES
    _CACHE.clear()
    _CACHE_HITS = 0
    _CACHE_MISSES = 0
