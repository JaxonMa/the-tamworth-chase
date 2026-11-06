"""Tests for the shipped campaign data."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from game.core import Simulation
from game.levels import load_levels, parse_level
from game.models import Direction, GameStatus, WinCondition

ROOT = Path(__file__).resolve().parent.parent
SOLUTIONS = json.loads((ROOT / "tests" / "solutions.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def levels():
    return load_levels()


def replay(level, solution):
    sim = Simulation(level, [tuple(pos) for pos in solution["obstacles"]])
    sim.start()
    for action in solution["actions"]:
        direction = None if action == "wait" else Direction[action.upper()]
        sim.order(direction)
    return sim


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


def test_all_levels_have_chinese_text(levels):
    for level in levels:
        assert level.name
        assert any("\u4e00" <= char <= "\u9fff" for char in level.name)
        assert level.hint


def test_all_levels_have_chase_fields(levels):
    for level in levels:
        assert level.max_turns >= 5
        assert 0 <= level.initial_obstacles <= 9
        assert 0 <= level.prediction_steps <= 20
        assert level.win_condition in (WinCondition.CATCH, WinCondition.PEN)
        if level.is_pen_level:
            assert level.pen_cells
        else:
            assert level.pen_cells == ()


def test_reference_solutions_win(levels):
    for level in levels:
        solution = SOLUTIONS[level.level_id]
        sim = replay(level, solution)
        assert sim.status is GameStatus.WON, f"{level.level_id} should be solvable"
        assert sim.turns == solution["turns"]
        assert sim.turns <= level.max_turns
        assert len(solution["obstacles"]) <= level.initial_obstacles


def test_solutions_reach_s_rank(levels):
    for level in levels:
        solution = SOLUTIONS[level.level_id]
        assert solution["turns"] <= level.s_threshold, (
            f"{level.level_id}: the optimal solution should reach S rank"
        )


def test_turn_limits_leave_room(levels):
    for level in levels:
        solution = SOLUTIONS[level.level_id]
        assert level.max_turns > solution["turns"]
        assert level.s_threshold < level.a_threshold < level.b_threshold


def test_levels_are_solvable_without_obstacles(levels):
    for level in levels:
        solution = SOLUTIONS[level.level_id]
        assert solution["obstacles"] == []
        assert replay(level, solution).status is GameStatus.WON


def test_parse_rejects_duplicate_farmer():
    with pytest.raises(Exception):
        parse_level(
            {
                "id": "dup",
                "name": "重复",
                "grid": ["#####", "#FFC#", "#...#", "#####"],
            }
        )


def test_parse_rejects_pen_level_without_cells():
    with pytest.raises(Exception):
        parse_level(
            {
                "id": "penless",
                "name": "没有围栏",
                "grid": ["#####", "#F..#", "#.C.#", "#####"],
                "win_condition": "pen",
            }
        )
