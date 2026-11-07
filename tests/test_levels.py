"""Tests for the shipped campaign data."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from game.core import Simulation
from game.levels import load_levels, parse_level
from game.models import Action, Actor, Direction, GameStatus
from game.levels import level_to_dict

ROOT = Path(__file__).resolve().parent.parent
SOLUTIONS = json.loads((ROOT / "tests" / "solutions.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def levels():
    return load_levels()


def replay(level, solution):
    sim = Simulation(level)
    for action in solution["actions"]:
        sim.apply_action(Action(action))
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


def test_all_levels_have_exit_fields(levels):
    for level in levels:
        assert level.exit_cells
        assert level.max_turns >= 5
        assert 0 <= level.prediction_steps <= 20
        assert not hasattr(level, "cow_behaviors")
        assert not (set(level.exit_cells) & level.wall_positions)
        assert not (set(level.exit_cells) & set(level.cow_positions))
        assert level.farmer_start not in level.exit_cells


def test_reference_solutions_win(levels):
    for level in levels:
        solution = SOLUTIONS[level.level_id]
        sim = replay(level, solution)
        assert sim.status is GameStatus.WON, f"{level.level_id} should be solvable"
        assert sim.turns == solution["turns"]
        assert sim.turns <= level.max_turns


def test_solutions_reach_s_rank(levels):
    for level in levels:
        solution = SOLUTIONS[level.level_id]
        assert solution["turns"] <= level.s_threshold, (
            f"{level.level_id}: the reference solution should reach S rank"
        )


def test_turn_limits_leave_room(levels):
    for level in levels:
        solution = SOLUTIONS[level.level_id]
        assert level.max_turns >= solution["turns"]
        assert level.s_threshold < level.a_threshold < level.b_threshold


def test_campaign_has_multi_cow_and_no_prediction_levels(levels):
    by_id = {level.level_id: level for level in levels}
    assert len(by_id["level_08"].cow_positions) == 2
    assert len(by_id["level_10"].cow_positions) == 2
    assert by_id["level_09"].prediction_steps == 0


def test_campaign_cows_use_the_unified_flee_behaviour(levels):
    by_id = {level.level_id: level for level in levels}
    sim = Simulation(by_id["level_06"])
    sim.farmer = Actor((2, 1), Direction.EAST)
    assert sim.cow_is_fleeing(0) is True
    assert not hasattr(by_id["level_06"], "cow_behaviors")


def test_level_to_dict_roundtrip(levels):
    for level in levels:
        payload = level_to_dict(level)
        restored = parse_level(payload)
        assert restored.exit_cells == level.exit_cells
        assert restored.cow_positions == level.cow_positions
        assert restored.max_turns == level.max_turns
        assert "cow_behavior" not in payload
        assert restored.obstacles == level.obstacles


def test_parse_rejects_duplicate_farmer():
    with pytest.raises(Exception):
        parse_level({"id": "dup", "name": "重复", "grid": ["#####", "#FFC#", "#...#", "#####"]})


def test_parse_rejects_exit_on_wall():
    with pytest.raises(Exception):
        parse_level(
            {
                "id": "badexit",
                "name": "坏出口",
                "grid": ["#####", "#F..#", "#.C.#", "#####"],
                "exit_cells": [[0, 0]],
            }
        )


def test_legacy_level_gets_a_default_exit():
    level = parse_level(
        {
            "id": "legacy",
            "name": "旧关卡",
            "grid": ["#######", "#F....#", "#..C..#", "#.....#", "#######"],
            "step_limit": 12,
            "obstacle_limit": 2,
            "cow_behavior": "seek_exit_and_flee",
        }
    )
    assert level.exit_cells
    assert level.extra.get("legacy_exit") is True
    assert level.max_turns == 12
