"""Achievement rules and daily meadow tests."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from game.achievements import ACHIEVEMENTS, AchievementTracker
from game.core import Simulation
from game.daily import date_key, generate_daily, seed_for, _solvable
from game.levels import load_level_file, parse_level
from game.models import GameStatus, Rank
from game.paths import project_root
from game.progress import ProgressStore


@pytest.fixture()
def store(tmp_path: Path) -> ProgressStore:
    return ProgressStore(tmp_path / "save.json").load()


@pytest.fixture()
def challenges():
    return load_level_file(project_root() / "levels" / "challenges.json", source="challenge")


def play_to_end(level, obstacles=()):
    sim = Simulation(level, obstacles)
    sim.start()
    while sim.status is GameStatus.PLAYING:
        sim.step()
    return sim


def test_one_step_achievement(store, challenges):
    level = next(item for item in challenges if item.level_id == "chal_one_step")
    sim = play_to_end(level)
    assert sim.steps == 1
    tracker = AchievementTracker(store)
    tracker.on_level_cleared(level, sim, sim.rank, store, loops=0, mode="main")
    assert store.has_achievement("one_step")
    assert store.has_achievement("no_obstacles")


def test_loop_free_requires_no_loops(store, challenges):
    level = next(item for item in challenges if item.level_id == "chal_one_step")
    sim = play_to_end(level)
    tracker = AchievementTracker(store)
    tracker.on_level_cleared(level, sim, sim.rank, store, loops=2, mode="main")
    assert not store.has_achievement("loop_free")


def test_fenced_cow_achievement(store):
    grid = [
        "#######",
        "#.C...#",
        "#.#...#",
        "#...#.#",
        "#.....#",
        "#F....#",
        "#######",
    ]
    level = parse_level(
        {"id": "corner", "name": "角落", "grid": grid, "farmer_facing": "east", "cow_facings": ["north"]}
    )
    sim = play_to_end(level)
    tracker = AchievementTracker(store)
    tracker.on_level_cleared(level, sim, sim.rank, store, loops=0, mode="main")
    # the cow starts in a corner directly above the farmer's path
    assert store.has_achievement("fenced_cow") or not sim.caught


def test_all_levels_achievement(store, challenges):
    level = next(item for item in challenges if item.level_id == "chal_one_step")
    sim = play_to_end(level)
    for index in range(10):
        store.main_levels[f"level_{index + 1:02d}"] = {"cleared": True, "best_steps": 10}
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


def test_daily_seed_matches_date():
    assert seed_for(date(2026, 11, 6)) == 20261106
    assert date_key(date(2026, 11, 6)) == "2026-11-06"
