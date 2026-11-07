"""Achievement rules and daily meadow tests."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from game.achievements import ACHIEVEMENTS, AchievementTracker
from game.core import Simulation
from game.daily import _solvable, date_key, generate_daily, seed_for
from game.levels import parse_level
from game.models import Action, GameStatus, Rank
from game.progress import ProgressStore


@pytest.fixture()
def store(tmp_path: Path) -> ProgressStore:
    return ProgressStore(tmp_path / "save.json").load()


def one_step_level(max_turns: int = 5):
    return parse_level(
        {
            "id": "one_step",
            "name": "一步",
            "grid": ["#######", "#...C.#", "#...F.#", "#.....#", "#######"],
            "fj_start_direction": "north",
            "cow_facings": ["west"],
            "exit_cells": [[1, 1]],
            "max_turns": max_turns,
        }
    )


def win_sim(level):
    sim = Simulation(level)
    sim.apply_action(Action.FORWARD)
    assert sim.status is GameStatus.WON
    return sim


def test_one_step_achievement(store):
    level = one_step_level()
    sim = win_sim(level)
    tracker = AchievementTracker(store)
    tracker.on_level_cleared(level, sim, sim.rank, store, loops=0, mode="main")
    assert store.has_achievement("one_step")
    assert store.has_achievement("flawless")


def test_close_call_achievement(store):
    level = one_step_level(max_turns=1)
    sim = win_sim(level)
    tracker = AchievementTracker(store)
    tracker.on_level_cleared(level, sim, sim.rank, store, loops=0, mode="main")
    assert store.has_achievement("close_call")


def test_flawless_requires_no_blocked_forward(store):
    level = parse_level(
        {
            "id": "blocked",
            "name": "撞墙",
            "grid": ["#######", "#F....#", "#...C.#", "#.....#", "#######"],
            "fj_start_direction": "north",
            "cow_facings": ["west"],
            "exit_cells": [[1, 5]],
            "max_turns": 20,
        }
    )
    sim = Simulation(level)
    sim.apply_action(Action.FORWARD)  # blocked by the border
    sim.farmer = sim.farmer.turned(sim.farmer.facing.clockwise())
    # The test only needs a WON state with blocked_events > 0.
    sim.status = GameStatus.WON
    tracker = AchievementTracker(store)
    tracker.on_level_cleared(level, sim, Rank.B, store, loops=0, mode="main")
    assert not store.has_achievement("flawless")


def test_loop_free_requires_no_loops(store):
    level = one_step_level()
    sim = win_sim(level)
    tracker = AchievementTracker(store)
    tracker.on_level_cleared(level, sim, sim.rank, store, loops=2, mode="main")
    assert not store.has_achievement("loop_free")


def test_all_levels_achievement(store):
    level = one_step_level()
    sim = win_sim(level)
    for index in range(10):
        store.main_levels[f"level_{index + 1:02d}"] = {"cleared": True, "best_turns": 10}
    tracker = AchievementTracker(store)
    tracker.on_level_cleared(level, sim, sim.rank, store, loops=0, mode="main")
    assert store.has_achievement("all_levels")


def test_achievements_are_unique_and_described():
    ids = [achievement.achievement_id for achievement in ACHIEVEMENTS]
    assert len(ids) == len(set(ids))
    for achievement in ACHIEVEMENTS:
        assert achievement.name and achievement.description


def test_daily_is_deterministic():
    first = generate_daily(date(2026, 5, 1))
    second = generate_daily(date(2026, 5, 1))
    assert first.level_id == second.level_id
    assert first.rows == second.rows
    assert first.source == "daily"
    assert first.exit_cells


def test_daily_varies_by_day():
    keys = {date_key(date(2026, 5, day)) for day in range(1, 8)}
    assert len(keys) == 7
    grids = {generate_daily(date(2026, 5, day)).rows for day in range(1, 8)}
    assert len(grids) > 1


def test_daily_is_solvable():
    for offset in range(3):
        level = generate_daily(date(2026, 6, 1) + timedelta(days=offset))
        assert _solvable(level)
        assert level.cow_behaviors


def test_daily_seed_matches_date():
    assert seed_for(date(2026, 11, 6)) == 20261106
    assert date_key(date(2026, 11, 6)) == "2026-11-06"


def test_rank_for_turns():
    level = one_step_level()
    assert level.rank_for(1) is Rank.S
