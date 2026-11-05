"""Tests for the shipped campaign data."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from game.core import Simulation
from game.levels import load_levels, parse_level
from game.models import GameStatus

ROOT = Path(__file__).resolve().parent.parent
SOLUTIONS = json.loads((ROOT / "tests" / "solutions.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def levels():
    return load_levels()


def test_campaign_has_ten_levels(levels):
    assert len(levels) == 10
    assert [level.level_id for level in levels] == [f"level_{i:02d}" for i in range(1, 11)]


def test_level_ids_unique(levels):
    ids = [level.level_id for level in levels]
    assert len(ids) == len(set(ids))


def test_all_levels_are_10x10(levels):
    for level in levels:
        assert level.width == 10
        assert level.height == 10


def test_all_levels_have_one_cow(levels):
    for level in levels:
        assert len(level.cow_positions) == 1


def test_all_levels_have_chinese_text(levels):
    for level in levels:
        assert level.name
        assert any("\u4e00" <= char <= "\u9fff" for char in level.name)
        assert level.hint


def test_reference_solutions_win(levels):
    for level in levels:
        solution = SOLUTIONS[level.level_id]
        obstacles = [tuple(pos) for pos in solution["obstacles"]]
        sim = Simulation(level, obstacles)
        sim.start()
        while sim.status is GameStatus.PLAYING:
            sim.step()
        assert sim.status is GameStatus.WON, f"{level.level_id} should be solvable"
        assert sim.steps <= level.step_limit
        assert len(obstacles) <= level.obstacle_limit


def test_solutions_are_optimal(levels):
    for level in levels:
        solution = SOLUTIONS[level.level_id]
        assert solution["steps"] <= level.s_threshold - 1, (
            f"{level.level_id}: the S rank must be reachable by the optimal solution"
        )


def test_step_limits_leave_room(levels):
    for level in levels:
        solution = SOLUTIONS[level.level_id]
        assert level.step_limit > solution["steps"]
        assert level.s_threshold < level.a_threshold < level.b_threshold < level.step_limit


def test_obstacle_limits_within_reference_solution(levels):
    for level in levels:
        solution = SOLUTIONS[level.level_id]
        assert len(solution["obstacles"]) <= level.obstacle_limit


def test_levels_are_not_solvable_with_zero_obstacles(levels):
    """Every campaign level should require at least one placed obstacle."""
    for level in levels:
        sim = Simulation(level, ())
        sim.start()
        while sim.status is GameStatus.PLAYING:
            sim.step()
        assert sim.status is not GameStatus.WON, f"{level.level_id} wins with no obstacles"


def test_parse_rejects_duplicate_farmer():
    with pytest.raises(Exception):
        parse_level(
            {
                "id": "dup",
                "name": "重复",
                "grid": ["#####", "#FFC#", "#...#", "#####"],
            }
        )
