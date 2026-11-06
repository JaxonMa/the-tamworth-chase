"""Achievement rules and daily meadow tests."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from game.achievements import ACHIEVEMENTS, AchievementTracker
from game.core import Simulation
from game.daily import _solvable, date_key, generate_daily, seed_for
from game.levels import parse_level
from game.models import Direction, GameStatus, Rank
from game.progress import ProgressStore


@pytest.fixture()
def store(tmp_path: Path) -> ProgressStore:
    return ProgressStore(tmp_path / "save.json").load()


def one_step_level():
    return parse_level(
        {
            "id": "one_step",
            "name": "一步",
            "grid": ["#######", "#FC...#", "#.....#", "#.....#", "#######"],
            "cow_facings": ["north"],
            "max_turns": 5,
        }
    )


def pen_level():
    return parse_level(
        {
            "id": "pen",
            "name": "围栏",
            "grid": ["#######", "#F....#", "#.C...#", "#.....#", "#######"],
            "cow_facings": ["east"],
            "win_condition": "pen",
            "pen_cells": [[2, 3]],
            "max_turns": 5,
        }
    )


def test_one_step_achievement(store):
    level = one_step_level()
    sim = Simulation(level)
    sim.start()
    sim.order(Direction.EAST)
    assert sim.status is GameStatus.WON and sim.turns == 1
    tracker = AchievementTracker(store)
    tracker.on_level_cleared(level, sim, sim.rank, store, loops=0, mode="main")
    assert store.has_achievement("one_step")
    assert store.has_achievement("no_obstacles")


def test_loop_free_requires_no_loops(store):
    level = one_step_level()
    sim = Simulation(level)
    sim.start()
    sim.order(Direction.EAST)
    tracker = AchievementTracker(store)
    tracker.on_level_cleared(level, sim, sim.rank, store, loops=2, mode="main")
    assert not store.has_achievement("loop_free")


def test_fenced_cow_achievement(store):
    level = pen_level()
    sim = Simulation(level)
    sim.start()
    sim.order(None)
    assert sim.status is GameStatus.WON and sim.all_penned
    tracker = AchievementTracker(store)
    tracker.on_level_cleared(level, sim, sim.rank, store, loops=0, mode="main")
    assert store.has_achievement("fenced_cow")


def test_all_levels_achievement(store):
    level = one_step_level()
    sim = Simulation(level)
    sim.start()
    sim.order(Direction.EAST)
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


def test_daily_varies_by_day():
    keys = {date_key(date(2026, 5, day)) for day in range(1, 8)}
    assert len(keys) == 7
    grids = {generate_daily(date(2026, 5, day)).rows for day in range(1, 8)}
    assert len(grids) > 1


def test_daily_is_solvable():
    for offset in range(3):
        level = generate_daily(date(2026, 6, 1) + timedelta(days=offset))
        assert _solvable(level)
        assert level.win_condition.value == "catch"
        assert level.max_turns >= 10


def test_daily_seed_matches_date():
    assert seed_for(date(2026, 11, 6)) == 20261106
    assert date_key(date(2026, 11, 6)) == "2026-11-06"


def test_rank_for_turns():
    level = one_step_level()
    assert level.rank_for(1) is Rank.S
